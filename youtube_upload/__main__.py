"""Enable ``python -m youtube_upload`` execution."""

import sys

import youtube_upload.main

if __name__ == "__main__":
    youtube_upload.main.main(sys.argv[1:])
