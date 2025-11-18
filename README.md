# Fusion Framework Library

## Introduction

This framework allows to develop new services based on generic basic blocs. It was created to ease maintainance of a modular ecosystem of cybersecurity services.

> [!TIP]
> This documentation does not aim for completeness but provides some keywords to `grep` to quickly locate the code which could answer the questions you may have.


## Structure

The framework is divided in four modules listed in the following table.

| Module | Description |
|:---------:|:-------------------------------------------|
| `client`  | Contains classes to build client applications to interact with server applications |
| `concept` | Contains concepts common to all services |
| `helper`  | Contains helpers to ease implementation of several tasks |
| `server`  | Contains classes to build server applications |


## Concept

In Fusion Framework, `Concept` is the interface for most objects shared between servers and clients. It implements serialization and deserialization methods allowing transparent conversion to and from JSON.

There are many subclasses of `Concept`, some are defined in this library as they are applicable to most client/server use-cases. Services can also derive `Concept` class to implement service-specific objects needed to exchange data between server and client.


## Server

Most important classes are listed in the following table.

| Class | Description |
|:---------:|:-------------------------------------------|
| `FusionAuthBackend` | Subclasses of this class perform authentication against different identity providers |
| `FusionAuthAPI`     | Implements authentication API for the server |
| `FusionCaseAPI`     | Implements case management API for the server |
| `FusionConstantAPI` | Implements hot-reload config API for the server |
| `FusionDownloadAPI` | Implements file download API for the server |
| `FusionEventAPI`    | Implements SSE and webhook APIs for the server |
| `FusionInfoAPI`     | Implements server information API |

Other important classes are located in these modules.

| Module | Description |
|:---------:|:-------------------------------------------|
| `config`       | Configuration classes |
| `storage`      | Data storage classes |
| `synchronizer` | Synchronizer classes |


## Client

Most important classes are listed in the following table.

| Class | Description |
|:---------:|:-------------------------------------------|
| `FusionClient` | Provides a generic client to handle communication with server mostly based on `Concept` subclasses |
| `FusionAuthAPIClient`     | Implements client for authentication API |
| `FusionCaseAPIClient`     | Implements client for case management API |
| `FusionConstantAPIClient` | Implements client for hot-reload config API |
| `FusionDownloadAPIClient` | Implements client for file download API |
| `FusionEventAPIClient`    | Implements client for SSE and webhook APIs |
| `FusionInfoAPIClient`     | Implements client for information API |


## Helper

Most important helpers are listed in the following table.

| Module | Description |
|:---------:|:-------------------------------------------|
| `aiohttp`     | Implements helpers for `aiohttp` operations across services |
| `config`      | Implements `ConfigError` and `load_ssl_config` helper |
| `datetime`    | Implements `datetime` serialization and deserialization |
| `filesystem`  | Implements helpers for filesystem operations across services |
| `flock`       | Implements file-based asynchronous locking |
| `logging`     | Implements logging helpers |
| `notifier`    | Implements `FusionNotifier` used for webhook and redis pubsub notifications |
| `pubsub`      | Implements publisher/subscriber notification queues (best effort) |
| `serializing` | Implements serialization (`Dumpable`) and deserialization (`Loadable`) |
| `streaming`   | Implements data streaming operations across services |
| `subprocess`  | Implements subprocess operations across services |
| `timer`       | Implements `Timer` |
| `tracing`     | Implements `trace_user_op` used to trace user operations across services |
| `zip`         | Implements archive creation (`create_zip`) and extraction (`extract_zip`) |
