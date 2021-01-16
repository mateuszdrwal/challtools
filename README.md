# challtools

challtools is a tool that manages CTF challenges and challenge repositories using the [OpenChallSpec](https://openchallspec.readthedocs.io/) challenge format.

## Installation

To install or upgrade challtools, run the following command:

```
pip3 install git+git://github.com/mateuszdrwal/challtools.git --upgrade
```

## Usage

### Validating

challtools includes a [OpenChallSpec](https://openchallspec.readthedocs.io/) validator. To validate that a challenge complies with the spec, run `challtools validate` in the challenge directory:

```
$ challtools validate
No issues raised.
Validation succeeded. No issues detected!
```

### Building

challtools can build docker containers and run build scripts defined in the challenge config for you. Running `challtools build` with a container defined in the configuration will build that container:

```
$ sudo challtools build
Flag: example{this_is_the_flag}
Processing container default...
Interpreting "container" as an image build directory
Building image...
Challenge built successfully!
```

Any solution containers will also be built in the same way.

challtools can also run custom build scripts, defined by adding something like this to the challenge config:

```yaml
custom:
  build_script: build.sh
```

This will run the `build.sh` file before any containers are built with the flag as a command line argument, allowing the flag to be inserted programmatically into the challenge. This eliminates any flag mismatches arising from the flag being defined in multiple places.

### Starting

challtools can start challenges for you. This is done by running `challtools start` in the challenge directory:

```
$ sudo challtools start
Started container default
Services:
nc 127.0.0.1 50000
```

### Solving

If a challenge solution is defined, challtools can verify that the challenge is solvable by automatically solving it. It does this by first building the challenge, starting it, starting the solution docker container and checking for if it outputs a flag. This is done using `challtools solve`:

```
$ sudo challtools solve
Started container default
Solving...
example{this_is_the_flag}

Challenge solved successfully!
```
