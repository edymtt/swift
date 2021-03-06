//===--- swift-reflection-dump.cpp - Reflection testing application -------===//
//
// This source file is part of the Swift.org open source project
//
// Copyright (c) 2014 - 2017 Apple Inc. and the Swift project authors
// Licensed under Apache License v2.0 with Runtime Library Exception
//
// See https://swift.org/LICENSE.txt for license information
// See https://swift.org/CONTRIBUTORS.txt for the list of Swift project authors
//
//===----------------------------------------------------------------------===//
// This is a host-side tool to dump remote reflection sections in swift
// binaries.
//===----------------------------------------------------------------------===//

#include "swift/ABI/MetadataValues.h"
#include "swift/Basic/LLVMInitialize.h"
#include "swift/Demangling/Demangle.h"
#include "swift/Reflection/ReflectionContext.h"
#include "swift/Reflection/TypeRef.h"
#include "swift/Reflection/TypeRefBuilder.h"
#include "llvm/ADT/StringSet.h"
#include "llvm/Object/Archive.h"
#include "llvm/Object/COFF.h"
#include "llvm/Object/ELF.h"
#include "llvm/Object/ELFObjectFile.h"
#include "llvm/Object/MachOUniversal.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/Error.h"

#if defined(_WIN32)
#include <io.h>
#else
#include <unistd.h>
#endif

#include <algorithm>
#include <csignal>
#include <iostream>

using llvm::ArrayRef;
using llvm::dyn_cast;
using llvm::StringRef;
using namespace llvm::object;

using namespace swift;
using namespace swift::reflection;
using namespace swift::remote;
using namespace Demangle;

enum class ActionType { DumpReflectionSections, DumpTypeLowering };

namespace options {
static llvm::cl::opt<ActionType> Action(
    llvm::cl::desc("Mode:"),
    llvm::cl::values(
        clEnumValN(ActionType::DumpReflectionSections,
                   "dump-reflection-sections",
                   "Dump the field reflection section"),
        clEnumValN(
            ActionType::DumpTypeLowering, "dump-type-lowering",
            "Dump the field layout for typeref strings read from stdin")),
    llvm::cl::init(ActionType::DumpReflectionSections));

static llvm::cl::list<std::string>
    BinaryFilename("binary-filename",
                   llvm::cl::desc("Filenames of the binary files"),
                   llvm::cl::OneOrMore);

static llvm::cl::opt<std::string>
    Architecture("arch",
                 llvm::cl::desc("Architecture to inspect in the binary"),
                 llvm::cl::Required);
} // end namespace options

template <typename T> static T unwrap(llvm::Expected<T> value) {
  if (value)
    return std::move(value.get());
  llvm::errs() << "swift-reflection-test error: " << toString(value.takeError())
               << "\n";
  exit(EXIT_FAILURE);
}

static void reportError(std::error_code EC) {
  assert(EC);
  llvm::errs() << "swift-reflection-test error: " << EC.message() << ".\n";
  exit(EXIT_FAILURE);
}

using NativeReflectionContext =
    swift::reflection::ReflectionContext<External<RuntimeTarget<sizeof(uintptr_t)>>>;

using ReadBytesResult = swift::remote::MemoryReader::ReadBytesResult;

static uint64_t getSectionAddress(SectionRef S) {
  // See COFFObjectFile.cpp for the implementation of 
  // COFFObjectFile::getSectionAddress. The image base address is added
  // to all the addresses of the sections, thus the behavior is slightly different from
  // the other platforms.
  if (auto C = dyn_cast<COFFObjectFile>(S.getObject()))
    return S.getAddress() - C->getImageBase();
  return S.getAddress();
}

static bool needToRelocate(SectionRef S) {
  if (!getSectionAddress(S))
    return false;

  if (auto EO = dyn_cast<ELFObjectFileBase>(S.getObject())) {
    static const llvm::StringSet<> ELFSectionsList = {
      ".data", ".rodata", "swift5_protocols", "swift5_protocol_conformances",
      "swift5_typeref", "swift5_reflstr", "swift5_assocty", "swift5_replace",
      "swift5_type_metadata", "swift5_fieldmd", "swift5_capture", "swift5_builtin"
    };
    StringRef Name;
    if (auto EC = S.getName(Name))
      reportError(EC);
    return ELFSectionsList.count(Name);
  }

  return true;
}


class Image {
  const ObjectFile *O;
  uint64_t VASize;

  struct RelocatedRegion {
    uint64_t Start, Size;
    const char *Base;
  };

  std::vector<RelocatedRegion> RelocatedRegions;

public:
  explicit Image(const ObjectFile *O) : O(O), VASize(O->getData().size()) {
    for (SectionRef S : O->sections()) {
      if (!needToRelocate(S))
        continue;
      auto SectionAddr = getSectionAddress(S);
      if (SectionAddr)
        VASize = std::max(VASize, SectionAddr + S.getSize());

     llvm::Expected<llvm::StringRef> Content = S.getContents();
      if (!Content)
        reportError(errorToErrorCode(Content.takeError()));

      auto PhysOffset = (uintptr_t)Content->data() - (uintptr_t)O->getData().data();
      
      if (PhysOffset == SectionAddr) {
        continue;
      }

      RelocatedRegions.push_back(RelocatedRegion{
        SectionAddr,
        Content->size(),
        Content->data()});
    }
  }

  RemoteAddress getStartAddress() const {
    return RemoteAddress((uintptr_t)O->getData().data());
  }

  bool isAddressValid(RemoteAddress Addr, uint64_t Size) const {
    auto start = getStartAddress().getAddressData();
    return start <= Addr.getAddressData()
      && Addr.getAddressData() + Size <= start + VASize;
  }

  ReadBytesResult readBytes(RemoteAddress Addr, uint64_t Size) {
    if (!isAddressValid(Addr, Size))
      return ReadBytesResult(nullptr, [](const void *) {});
    
    auto addrValue = Addr.getAddressData();
    auto base = O->getData().data();
    auto offset = addrValue - (uint64_t)base;
    for (auto &region : RelocatedRegions) {
      if (region.Start <= offset && offset < region.Start + region.Size) {
        // Read shouldn't need to straddle section boundaries.
        if (offset + Size > region.Start + region.Size)
          return ReadBytesResult(nullptr, [](const void *) {});

        offset -= region.Start;
        base = region.Base;
        break;
      }
    }
    
    return ReadBytesResult(base + offset, [](const void *) {});
  }
};

class ObjectMemoryReader : public MemoryReader {
  std::vector<Image> Images;

public:
  explicit ObjectMemoryReader(
      const std::vector<const ObjectFile *> &ObjectFiles) {
    for (const ObjectFile *O : ObjectFiles)
      Images.emplace_back(O);
  }

  const std::vector<Image> &getImages() const { return Images; }

  bool queryDataLayout(DataLayoutQueryType type, void *inBuffer,
                       void *outBuffer) override {
    switch (type) {
    case DLQ_GetPointerSize: {
      auto result = static_cast<uint8_t *>(outBuffer);
      *result = sizeof(void *);
      return true;
    }
    case DLQ_GetSizeSize: {
      auto result = static_cast<uint8_t *>(outBuffer);
      *result = sizeof(size_t);
      return true;
    }
    }

    return false;
  }

  RemoteAddress getSymbolAddress(const std::string &name) override {
    return RemoteAddress(nullptr);
  }

  ReadBytesResult readBytes(RemoteAddress Addr, uint64_t Size) override {
    auto I = std::find_if(Images.begin(), Images.end(), [=](const Image &I) {
      return I.isAddressValid(Addr, Size);
    });
    return I == Images.end() ? ReadBytesResult(nullptr, [](const void *) {})
                             : I->readBytes(Addr, Size);
  }

  bool readString(RemoteAddress Addr, std::string &Dest) override {
    ReadBytesResult R = readBytes(Addr, 1);
    if (!R)
      return false;
    StringRef Str((const char *)R.get());
    Dest.append(Str.begin(), Str.end());
    return true;
  }
};

static int doDumpReflectionSections(ArrayRef<std::string> BinaryFilenames,
                                    StringRef Arch, ActionType Action,
                                    std::ostream &OS) {
  // Note: binaryOrError and objectOrError own the memory for our ObjectFile;
  // once they go out of scope, we can no longer do anything.
  std::vector<OwningBinary<Binary>> BinaryOwners;
  std::vector<std::unique_ptr<ObjectFile>> ObjectOwners;
  std::vector<const ObjectFile *> ObjectFiles;

  for (const std::string &BinaryFilename : BinaryFilenames) {
    auto BinaryOwner = unwrap(createBinary(BinaryFilename));
    Binary *BinaryFile = BinaryOwner.getBinary();

    // The object file we are doing lookups in -- either the binary itself, or
    // a particular slice of a universal binary.
    std::unique_ptr<ObjectFile> ObjectOwner;
    const ObjectFile *O = dyn_cast<ObjectFile>(BinaryFile);
    if (!O) {
      auto Universal = cast<MachOUniversalBinary>(BinaryFile);
      ObjectOwner = unwrap(Universal->getObjectForArch(Arch));
      O = ObjectOwner.get();
    }

    // Retain the objects that own section memory
    BinaryOwners.push_back(std::move(BinaryOwner));
    ObjectOwners.push_back(std::move(ObjectOwner));
    ObjectFiles.push_back(O);
  }

  auto Reader = std::make_shared<ObjectMemoryReader>(ObjectFiles);
  NativeReflectionContext Context(Reader);
  for (const Image &I : Reader->getImages())
    Context.addImage(I.getStartAddress());

  switch (Action) {
  case ActionType::DumpReflectionSections:
    // Dump everything
    Context.getBuilder().dumpAllSections(OS);
    break;
  case ActionType::DumpTypeLowering: {
    for (std::string Line; std::getline(std::cin, Line);) {
      if (Line.empty())
        continue;

      if (StringRef(Line).startswith("//"))
        continue;

      Demangle::Demangler Dem;
      auto Demangled = Dem.demangleType(Line);
      auto *TypeRef =
          swift::Demangle::decodeMangledType(Context.getBuilder(), Demangled);
      if (TypeRef == nullptr) {
        OS << "Invalid typeref: " << Line << "\n";
        continue;
      }

      TypeRef->dump(OS);
      auto *TypeInfo =
          Context.getBuilder().getTypeConverter().getTypeInfo(TypeRef);
      if (TypeInfo == nullptr) {
        OS << "Invalid lowering\n";
        continue;
      }
      TypeInfo->dump(OS);
    }
    break;
  }
  }

  return EXIT_SUCCESS;
}

int main(int argc, char *argv[]) {
  PROGRAM_START(argc, argv);
  llvm::cl::ParseCommandLineOptions(argc, argv, "Swift Reflection Dump\n");
  return doDumpReflectionSections(options::BinaryFilename,
                                  options::Architecture, options::Action,
                                  std::cout);
}
