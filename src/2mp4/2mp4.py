
import argparse
import os
import re
import sh
import sys

from cStringIO import StringIO
from progressbar import (
    ProgressBar,
    Percentage,
    Bar,
    ETA,
    FileTransferSpeed,
    Timer
)
from pymediainfo import MediaInfo


class AttrDict(dict):
    def __init__(self, *a, **kw):
        dict.__init__(self, *a, **kw)
        self.__dict__ = self


def get_media_info(file):
    result = AttrDict()
    xmlIO  = StringIO()
    sh.mediainfo(
        '--Output=XML',
        '-f', file,
        _out=xmlIO
    )
    mediainfo = MediaInfo(xmlIO.getvalue())
    for track in mediainfo.tracks:
        if track.track_type == 'Video':
            result.video = track
        elif track.track_type == 'Audio':
            result.audio = track
        elif track.track_type == 'Text':
            result.text = track
        elif track.track_type == 'General':
            result.general = track
        else:
            raise Exception('Enexpected track type: %s' % track.track_type)

    return result


class EncodingProgress:
    FRAMES_RE = re.compile(r'^frame=\s*(\d+) .*')
    def __init__(self, title, total_frames):
        widgets = [
            title,
            Percentage(), ' ',
            Bar(), ' ',
            Timer(), ' ',
            ETA(), ' ',
            FileTransferSpeed(unit='Frames')
        ]
        print total_frames
        self.pbar = ProgressBar(
            widgets=widgets,
            maxval=int(total_frames),
            term_width=120
        )
        self.pbar.start()

    def process_ffmpeg_line(self, line):
        lines = line.splitlines()
        for l in lines:
            match = self.FRAMES_RE.match(l)
            if match is not None:
                frame = int(match.groups()[0])
                if frame > self.pbar.maxval:
                    self.pbar.update(value=self.pbar.maxval)
                else:
                    try:
                        self.pbar.update(value=frame)
                    except Exception as e:
                        print 'Frame: %s, error: %s' % (frame, e.message)
                        print line

    def finish(self):
        self.pbar.finish()


def convert(info, file):
    if info.video.format == 'AVC':
        method = '1pass'
        video_opts = [
            '-codec:v', 'copy'
        ]
    else:
        method = '2pass'
        video_opts = [
            '-b:v', info.video.bit_rate,
            '-codec:v', 'libx264',
            '-profile:v', 'high',
            '-level', '4.1'
        ]

    if info.audio.format == 'AAC':
        audio_opts = [
            '-codec:a', 'copy'
        ]
    else:
        audio_opts = [
            '-codec:a', 'libfaac',
            '-b:a', '160K'
        ]

    input_ops = [
        '-i', '%s' % file,
    ]

    sh.vmtouch(
        '-m', '10G',
        '-vt',
        file,
        _bg=True
    )
    out_file_name = '%s.mp4' % info.general.file_name
    sys.stderr.write('Encoding %s -> %s\n' % (file, out_file_name))
    sys.stdout.write('Encoding %s -> %s\n' % (file, out_file_name))
    if method == '1pass':
        opts = input_ops + video_opts + audio_opts + [
            #'-threads', '4',
            '-y',
            os.path.join(info.general.folder_name, out_file_name)
        ]
        progress = EncodingProgress('Pass 1 of 1:', info.video.frame_count)
        p = sh.ffmpeg(
            *opts,
            _err=progress.process_ffmpeg_line,
            _err_bufsize=256
        )
        p.wait()
        progress.finish()
    elif method == '2pass':
        pass1_progress = EncodingProgress('Pass 1 of 2: ', info.video.frame_count)
        opts = input_ops + video_opts + [
            '-an',
            '-pass', '1',
            '-threads', '4',
            '-y',
            '-f', 'rawvideo',
            '/dev/null'
        ]
        p = sh.ffmpeg(
            *opts,
            _err=pass1_progress.process_ffmpeg_line,
            _err_bufsize=256
        )
        p.wait()
        pass1_progress.finish()

        pass2_progress = EncodingProgress('Pass 2 of 2: ', info['video']['frame_count'])
        opts = input_ops + video_opts + audio_opts + [
            '-pass', '2',
            '-threads', '8',
            '-y',
            '%s/%s' % (info['dir'], out_file_name)
        ]
        p = sh.ffmpeg(
            *opts,
            _err=pass2_progress.process_ffmpeg_line,
            _err_bufsize=256
        )
        p.wait()
        pass2_progress.finish()


def main():
    parser = argparse.ArgumentParser(
        prog=__name__.split('.')[0]
    )
    parser.add_argument(
        '-f', '--file',
        required=True
    )
    args = parser.parse_args()
    filename = args.file.strip()
    info = get_media_info(filename)
    convert(info, filename)

