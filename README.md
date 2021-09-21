# clrenv

A tool to give easy access to environment yaml file to python.

## Getting Started

* Install clrenv
```
$ git+https://github.com/color/clrenv.git@v0.1.6
```

* Create a file called `environment.yaml`.
```
# environment.yaml
base:
  name: foo
  location: sf
```

* Set a path to the file.
```
$ export CLRENV_PATH=/path/to/environment.yaml
```

* Access env varianble from python
```
> from clrenv import env
> env.name
=> "foo"
> env.location
=> "sf"
```

## Add a mode

* Edit the `environment.yaml` file.
```
# environment.yaml
base:
  name: foo
  location: sf

production:
  location: nyc
```

* Set a mode:
```
$ export CLRENV_MODE=production
```

* Access env varianble from python
```
> from clrenv import env
> env.name
=> "foo"
> env.location
=> "nyc"
```

## Add an overlay

* Create a file called `environment.overlay.yaml`.
```
# environment.overlay.yaml
base:
  name: bar
```

* Set a path to the file.
```
$ export CLRENV_OVERLAY_PATH=/path/to/environment.overlay.yaml
```

* Access env variable from python
```
> from clrenv import env
> env.name
=> "bar"
> env.location
=> "sf"
```

`CLRENV_OVERLAY_PATH` may have multiple files separated by `:`, e.g. `/path/foo.overlay.yaml:/path/bar.overlay.yaml`.

## Development
* Create a virtualenv and activate it
```
python3 -m venv_clrenv <location>
source <location>/bin/activate
```
* Install this package as editable (symlinked to source files)
```
pip install -e .
pip install black isort
```
* Run the tests
```
$ pytest --cov
$ mypy clrenv
$ pytest --cov-report=term --cov-report=html --cov
$ mypy --no-implicit-optional  --warn-redundant-casts  --warn-return-any --warn-unreachable --warn-unused-ignores --pretty --txt-report /tmp --html-report /tmp clrenv/*py
$ cat /tmp/index.txt
$ black .
$ isort .
```
