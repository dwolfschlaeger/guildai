 Guild check

Check:

    >>> run("guild check --offline")
    guild_version:             0.7...
    guild_install_location:    ...
    guild_home:                ...
    guild_resource_cache:      ...
    installed_plugins:         cpu, disk, exec_script, gpu, keras, memory, perf, python_script, queue, skopt
    python_version:            ...
    python_exe:                ...
    platform:                  ...
    psutil_version:            5.6.3
    tensorboard_version:       ...
    cuda_version:              ...
    nvidia_smi_version:        ...
    latest_guild_version:      unchecked (offline)
    <exit 0>

Show more check info with the `-v` (verbose) option:

    >>> run("guild check -v --offline")
    guild_version:             ...
    ...
    click_version:             7.1.2
    distutils_version:         ...
    numpy_version:             ...
    pandas_version:            not installed (No module named ...pandas...)
    pip_version:               18.0
    sklearn_version:           ...
    skopt_version:             ...
    setuptools_version:        ...
    twine_version:             ...
    yaml_version:              5...
    werkzeug_version:          1...
    latest_guild_version:      unchecked (offline)
    <exit 0>

TensorFlow info:

    >>> run("guild check --offline --tensorflow")
    guild_version:             ...
    tensorflow_version:        not installed
    ...
    <exit 0>

PyTorch info:

    >>> run("guild check --offline --pytorch")
    guild_version:             ...
    pytorch_version:           not installed
    ...
    <exit 0>

NOTE: twine version is not asserted because it's a test dep that isn't
always available when this test is run.

Show with disk usage:

    >>> run("guild check --offline --space")
    guild_version:             ...
    disk_space:
      guild_home:              ...
      runs:                    ...
      deleted_runs:            ...
      remote_state:            ...
      cache:                   ...
    <exit 0>

We should also see Guild environment files in our workspace:

    >>> run("cd $WORKSPACE && find .guild | LC_ALL=C sort")
    .guild
    .guild/.guild-nocopy
    .guild/cache
    .guild/cache/resources
    .guild/cache/runs
    .guild/runs
    .guild/trash
    <exit 0>
