# dboxsync

Dropbox synchronization tool for servers.

Features:

 - Download a folder or file from Dropbox
 - Keep a local folder or file in sync with Dropbox (read-only)
 - Upload a file to Dropbox
 - Triggers a command when a file changes on Dropbox

## Configuration

dboxsync uses an INI configuration file. It needs at least a `[dropbox]` section
with an `api_key` and `api_secret` key. You can initialize a configuration
file by simply running the utility without any arguments.

You can define which folders to keep in sync in the `[sync]` section. Keys should
be path on Dropbox and values the local path where to download the file.

You can define commands to trigger when a file changes on Dropbox in the `[watch]`
section. Keys should be path on Dropbox and values a shell command to execute.

The `[sync]` and `[watch]` sections are optional.

Example:

    [dropbox]
    api_key = aaaaaaaaaa
    api_secret = bbbbbbbbbbbb

    [sync]
    /my_file.txt = /home/user/my_file.txt
    /my_dir = /home/user/my_dir

    [watch]
    /my_other_file.txt = echo "hello world"

## Usage

You can simply run the dboxsync binary without any configuration. It will look
for a configuration file name `dboxsync.ini` in the current directory. You can
specify another one using `-c`.

When running without commands, dboxsync uses the configuration file.

You can sync files or folders using the sync command:

    $ dboxsync sync /my_file.txt
    $ dboxsync sync /my_folder
    $ dboxsync sync /my_file.txt /home/user/alias.txt

The state of synchronization is maintained inside dotfiles inside the synchronized
directory or beside a synchronized file.

You can simply download a file or folder using the download command. Works
like sync but does not maintain the state of synchronization.

You can upload a file or folder using the upload command:

    $ dboxsync upload my_file.txt
    $ dboxsync upload my_file.txt /folder/file.txt

You can watch for remote file modifications and execute a command using the
watch command:

    $ dboxsync watch /my_file.txt 'echo "hello world"'

