from conans import ConanFile

class Pkg(ConanFile):
    name = "lipo-variants-middleware"
    version = "0.1"
    python_requires = "lipo-middleware/0.1"
    build_policy = "missing"

    def middleware(self):
        Lipo = self.python_requires["lipo-middleware"].module.Lipo
        variants = [
            {
                "display_name": "x86_64",
                "arch": "x86_64",
                "os.version": "10.13"
            },
            {
                "display_name": "armv8",
                "arch": "armv8",
                "os.version": "11.0"
            }
        ]
        def factory(conanfile):
            return Lipo(conanfile, variants=variants)
        return factory
