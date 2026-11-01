# World overlay adaptations

Upstream: patch-gg/pixelfx, snapshot a84159688af3ca37a4be05a0d422b94451b2e24e. Preserve LICENSE and NOTICE.md, including Sprite Fusion/Hugo Duprez attribution in source files.

Selected source modules and core are vendored under src/. Cloud rendering omits the moon/halo so the same clouds can serve daytime and nighttime. Rain omits its full-frame haze, floor fill and back mist; drops and splashes remain transparent. Fog is unchanged. No Patch font or gallery asset is used.

`overlay/prepare-world-effects.mjs` exports 6 fps PNG sheets and metadata using the shared local PixelFX renderer (its absolute path is machine-specific development tooling). The runtime reads only project-local PNGs, not the shared library or Node.
