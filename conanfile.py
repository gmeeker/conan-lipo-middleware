import os
import shutil

from conans import ConanFile, ConanVariantsMiddleware, tools
from conans.errors import ConanException
from conans.model.conan_file import get_env_context_manager
from conans.client.tools.apple import is_apple_os
from conans.client.build.cmake_flags import get_generator


required_conan_version = ">=1.40.0"

# These are for optimization only, to avoid unnecessarily reading files.
_binary_exts = ['.a', '.dylib']
_regular_exts = [
    '.h', '.hpp', '.hxx', '.c', '.cc', '.cxx', '.cpp', '.m', '.mm', '.txt', '.md', '.html', '.jpg', '.png'
]

def is_macho_binary(filename):
    ext = os.path.splitext(filename)[1]
    if ext in _binary_exts:
        return True
    if ext in _regular_exts:
        return False
    with open(filename, "rb") as f:
        header = f.read(4)
        if header == b'\xcf\xfa\xed\xfe':
            # cffaedfe is Mach-O binary
            return True
        elif header == b'\xca\xfe\xba\xbe':
            # cafebabe is Mach-O fat binary
            return True
        elif header == b'!<arch>\n':
            # ar archive
            return True
    return False

def copy_variant_file(conanfile, src, dst, top=None, variants=[]):
    if os.path.isfile(src):
        if top and variants and is_macho_binary(src):
            # Try to lipo all available variants on the first path.
            src_components = src.split(os.path.sep)
            top_components = top.split(os.path.sep)
            if src_components[:len(top_components)] == top_components:
                variant_dir = src_components[len(top_components)]
                subpath = src_components[len(top_components) + 2:]
                variant_paths = [os.path.join(*([top, variant_dir, variant] + subpath)) for variant in variants]
                variant_paths = [p for p in variant_paths if os.path.isfile(p)]
                if len(variant_paths) > 1:
                    conanfile.run(['lipo', '-create', '-output', dst] + variant_paths)
                    return
        if os.path.exists(dst):
            pass # don't overwrite existing files
        else:
            shutil.copy2(src, dst)

# Modified copytree to copy new files to an existing tree.
def graft_tree(src, dst, symlinks=False, copy_function=shutil.copy2, dirs_exist_ok=False):
    names = os.listdir(src)
    os.makedirs(dst, exist_ok=dirs_exist_ok)
    errors = []
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        if os.path.exists(dstname):
            continue
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                graft_tree(srcname, dstname, symlinks, copy_function, dirs_exist_ok)
            else:
                copy_function(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except OSError as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive graft_tree so that we can
        # continue with other files
        except shutil.Error as err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except OSError as why:
        # can't copy file access times on Windows
        if why.winerror is None:
            errors.extend((src, dst, str(why)))
    if errors:
        raise shutil.Error(errors)

class patch_arguments:
    def __init__(self, target, name, func):
        self._target = target
        self._name = name
        self._func = func

    def __call__(self, *args, **kw):
        return self._func(self._original, *args, **kw)

    def __enter__(self):
        self._original = getattr(self._target, self._name)
        setattr(self._target, self._name, self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        setattr(self._target, self._name, self._original)

class Lipo(ConanVariantsMiddleware):
    def __init__(self, *args, **kw):
        super().__init__(*args, localattrs=['_can_lipo'], **kw)
        # Recipe handles this itself
        self._can_lipo = self.is_xcode() or self.settings.get_safe("multiarch", None)

    """ If the user is using Xcode, we assume they are using a custom toolchain for multiarch. """
    def is_xcode(self):
        if "cmake" in self.generators:
            with get_env_context_manager(self):
                if get_generator(self) == "Xcode":
                    return True
        return False

    def is_binary(self):
        try:
            if self.options.header_only:
                # Header only
                return None
        except ConanException:
            pass
        try:
            self.settings.arch
            if not is_apple_os(self.settings.os):
                return None
        except ConanException:
            # arch or os is not required
            return None
        return True

    def valid(self):
        if not self.is_binary():
            return False
        if self._can_lipo:
            return True
        return len(super().variants() or ()) > 1

    def variants(self):
        if not self.is_binary():
            return None
        if self._can_lipo:
            return None
        return super().variants()

    @staticmethod
    def xcode_copy(copy, *args, excludes=(), **kw):
        # Some packages (libpng) use cmake but package with self.copy("*")
        # so make sure that we don't find the single arch files.
        copy(*args, excludes=excludes + ["*Objects-normal"], **kw)

    def package(self):
        with patch_arguments(self.get_conanfile(), "copy", self.xcode_copy):
            if self.is_binary() and self._can_lipo:
                return self.conanfile.package()
            self.package_variants()
        variants = self.valid() and self.variants()
        if not variants:
            return
        package_folder = self.package_folder
        variant_folders = [self.get_variant_folder(None, v) for v in variants]
        for v in variants:
            graft_tree(self.get_variant_folder(package_folder, v),
                       package_folder,
                       symlinks=True,
                       copy_function=lambda s, d: copy_variant_file(self, s, d, top=package_folder, variants=variant_folders),
                       dirs_exist_ok=True)
        shutil.rmtree(os.path.join(package_folder, self.variants_folder))

    def test(self):
        self.test_variants()

    def package_id(self):
        if self.is_binary():
            variants = self.valid() and self.variants()
            if variants or self._can_lipo:
                return self.package_id_variants()
        return super().package_id()

class LipoMiddleware(ConanFile):
    name = "lipo-middleware"
    version = "0.1"
