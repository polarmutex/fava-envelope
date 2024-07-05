# Changelog

## [0.5.9](https://github.com/polarmutex/fava-envelope/compare/v0.5.8...v0.5.9) (2024-07-05)


### Bug Fixes

* add check to row to prevent error ([1332490](https://github.com/polarmutex/fava-envelope/commit/133249066ede736aff56745f661ca5c2d00ca71d))
* allow more than one allocate in a given month ([4340381](https://github.com/polarmutex/fava-envelope/commit/4340381f8ef7db6a32ce0279e631d029c28b9083))

## [0.5.8](https://github.com/polarmutex/fava-envelope/compare/v0.5.7...v0.5.8) (2023-09-17)


### Bug Fixes

* pandas v2 upgrade ([653befa](https://github.com/polarmutex/fava-envelope/commit/653befac73f17000935dbdd4efc43f5e4f6f212a))

## [0.5.7](https://github.com/polarmutex/fava-envelope/compare/v0.5.6...v0.5.7) (2023-09-17)


### Bug Fixes

* fava new release change ([5328f71](https://github.com/polarmutex/fava-envelope/commit/5328f71ba0d37f3c0cd991526c761819c449001a))
* github action release ([66fd333](https://github.com/polarmutex/fava-envelope/commit/66fd333c4765bb1f450a91fde64b79eac9a08e89))

## [0.5.6](https://github.com/polarmutex/fava-envelope/compare/v0.5.5...v0.5.6) (2022-10-25)


### Bug Fixes

* pypi release builds ([6479022](https://github.com/polarmutex/fava-envelope/commit/6479022d08d2b226687dfe133e06a13f93896151))

## [0.5.5](https://github.com/polarmutex/fava-envelope/compare/v0.5.4...v0.5.5) (2022-10-24)


### Bug Fixes

* error from pre-commit ([3998f9c](https://github.com/polarmutex/fava-envelope/commit/3998f9c08fb4892d10e34fef475787a89a9ad08d))
* fava ledger.entries deprecation ([39016f4](https://github.com/polarmutex/fava-envelope/commit/39016f444b5de4a1564081317f41131a4fa8ad1f))
* html files not included on install ([871e78a](https://github.com/polarmutex/fava-envelope/commit/871e78aac1503627d9525d4c7f87929bb1483956))
* nix to use poetry2nix ([e972bec](https://github.com/polarmutex/fava-envelope/commit/e972bec9fdcfcebbdd20891e809867362047872c))

### [0.5.4](https://github.com/polarmutex/fava-envelope/compare/v0.5.3...v0.5.4) (2022-05-19)


### Bug Fixes

* [#34](https://github.com/polarmutex/fava-envelope/issues/34) remove unused line in example ([d88d52c](https://github.com/polarmutex/fava-envelope/commit/d88d52c8e303a3ea5af9f23535c552d3632d9692))
* security dependency updates ([3e8d4b6](https://github.com/polarmutex/fava-envelope/commit/3e8d4b6f3cf47725c70e4ed4a703139c4fa4f073))


### Documentation

* changlog edits ([fe6fc3a](https://github.com/polarmutex/fava-envelope/commit/fe6fc3a3dba23fcdffad5f0eb1822496afe371b3))
* changlog edits ([c1e59e0](https://github.com/polarmutex/fava-envelope/commit/c1e59e0bbe9f6640a793610bf5a7aac1a0be7d1c))

### [0.5.3](https://github.com/polarmutex/fava-envelope/compare/v0.5.2...v0.5.3) (2022-05-19)

### Features

* Added negative rollover option
* Add rudimentary ability to see future months

### Bug Fixes

* replace url_for_current with url_for (for compatibility with fava 1.20 and up) ([910b3ad](https://github.com/polarmutex/fava-envelope/commit/910b3ad742683e747660c09430e56415ee44d8c3))

### [0.5.2](https://github.com/polarmutex/fava-envelope/compare/v0.5.1...v0.5.2) (2021-07-19)

### Bug Fixes

* bug where tables were not displaying on the latest fava

### [0.5.1](https://github.com/polarmutex/fava-envelope/compare/0.5...v0.5.1) (2021-01-29)

### Features

* Adding multiple budgets in multiple currencies capacity to fava_envelope

### Bug Fixes

* bug where it would not load page for month selected
* add checks for lastest fava which changed querytable api
* Fixed a typo in get_currencies()
* probably should not hard code 2020
* allow months with no income by setting the default to 0
* use beancounts operating_currency if available
