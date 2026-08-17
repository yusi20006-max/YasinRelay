# YasinRelay Termux Bootstrap

YasinRelay treats Termux/Android as a first-class deployment target.

The installer provisions the native Termux toolchain, creates the virtual environment, installs the Relay package and tests, builds the Go fetcher, and validates the CLI.

## Runtime configuration

Installation does not invent credentials. `EITAA_TOKEN` and `EITAA_CHANNEL` must be supplied by the operator before real publishing.

`SOURCE_CHANNELS` is optional at install time. If it is empty, the runtime must report a configuration state instead of crashing with an unhandled error.

When a sibling `../Yasin-AI` checkout exists, the Termux bootstrap should install it into the Relay virtual environment so the canonical Yasin-AI contracts are available to Relay.
