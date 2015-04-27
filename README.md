2mp4 [![Build Status](https://travis-ci.org/skonakov/2mp4.svg?branch=master)](https://travis-ci.org/skonakov/2mp4)
====
Easily convert video files to .mp4

Description
-----------

'2mp4' is a utility that simplifies conversion of video files to mp4 format.
It uses 'ffmpeg' with 'libx264' to do the required video and audio
conversion.

Installation
------------

1. Install ffmpeg version 1.0 or greater
1. Install mediainfo
1. Install 2mp4

```
$ [sudo] pip install 2mp4
```

Usage
-----

```
$ 2mp4 -h
usage: 2mp4 [-h] [-n] [-f] [-v] input_file

Convert [input_file] to mp4. The output video file will be created in the same
directory named [input_file].mp4

positional arguments:
  input_file          file or directory to convert to mp4

optional arguments:
  -h, --help          show this help message and exit
  -n, --dry-run       Don't actually do the conversion, just show the
                      command(s) that would be executed
  -f, --force-encode  Force a re-encode of the video stream, even if it is
                      already in a format supported by mp4 container.
  -v, --version       show program's version number and exit
```

