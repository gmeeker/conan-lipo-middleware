from conans import ConanFile

class Pkg(ConanFile):
    name = "lipo-multiarch-middleware"
    version = "0.1"
    python_requires = "lipo-middleware/0.1"
    settings = "multiarch"
    build_policy = "missing"

    def middleware(self):
        Lipo = self.python_requires["lipo-middleware"].module.Lipo
        multiarch = self.settings.multiarch
        if multiarch:
            def factory(conanfile):
                return Lipo(conanfile, variants=multiarch)
            return factory
        return None
