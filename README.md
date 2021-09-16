# Conan universal binary support on macOS/iOS

## Purpose

The Conan C++ package manager is designed to build one binary package per architecture, however, macOS and iOS can bundle multiple architectures into one file (called a universal or fat binary).  CMake supports multiple architectures, but many recipes use autotools or other methods.  Ideally Conan could handle all these cases:

1. CMake recipes build for multiple architectures (currently Conan requires a custom toolchain)
2. Recipes can handle this themselves, for example if they call xcodebuild with Xcode project files.
3. The other recipes in CCI should work without changes, by calling build() multiple times and joining with lipo (macOS/iOS).

This was discussed in this GitHub issue:
<https://github.com/conan-io/conan/issues/1047>

## Conan requirements

This requires the proposed Conan middleware support, in the *middleware* branch:
<https://github.com/gmeeker/conan>

## Installation

Install the Lipo class:

``$ conan create .``

Install the package to use *multiarch*, or derive your own and pass additional settings to each variant (e.g. different SDKs for iOS).

``$ cd multiarch && conan create .``

### Settings

Create a new profile, e.g. *universal*:

```
[settings]
os=Macos
os_build=Macos
os.version=10.13
multiarch=x86_64 armv8
arch=x86_64
arch_build=x86_64
compiler=apple-clang
compiler.version=12.0
compiler.libcxx=libc++
build_type=Release
compiler.cppstd=11
[options]
[build_requires]
lipo-multiarch-middleware/0.1@
[env]
```

### CMake and Xcode

CMake supports multiple architectures with CMAKE_OSX_ARCHITECTURES only if the Xcode generator is used.  However, not all upstream packages compile correctly with the Xcode generator, and some packages won't configure multiple architectures correctly.  While it won't work for all CCI recipes, it's still useful for your own recipes.  If you configure a toolchain with the Xcode generator, lipo will not be used.  If a recipes uses the multiarch setting (perhaps calling xcodebuild directly), lipo will not be used either.

One approach is here: <https://github.com/gmeeker/conan-darwin-toolchain> which is forked from <https://github.com/theodelrieu/conan-darwin-toolchain> and updated for multiple architectures.  (Not yet updated to use the multiarch setting.)  Add the package to [build_requires].

```
darwin-toolchain/1.0.9@gmeeker/stable
```
