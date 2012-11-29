
import argparse
import re
import sh
import sys

from progressbar import (
    ProgressBar,
    Percentage,
    Bar,
    ETA,
    FileTransferSpeed,
    Timer
)


class AttrDict(dict):
    def __init__(self, *a, **kw):
        dict.__init__(self, *a, **kw)
        self.__dict__ = self


def get_media_info(file):
    mediainfo = sh.mediainfo.bake(file)
    return AttrDict(
        format=mediainfo(inform='General;%Format%').strip(),
        file_name=mediainfo(inform='General;%FileName%').strip(),
        file_extension=mediainfo(inform='General;%FileExtension%').strip(),
        dir=mediainfo(inform='General;%FolderName%').strip(),
        video=AttrDict(
            bit_rate=mediainfo(inform='Video;%BitRate%').strip(),
            duration=mediainfo(inform='Video;%Duration%').strip(),
            size=mediainfo(inform='Video;%StreamSize%').strip(),
            format=mediainfo(inform='Video;%Format%').strip(),
            frame_count=mediainfo(inform='Video;%FrameCount%').strip()
        ),
        audio=AttrDict(
            bit_rate=mediainfo(inform='Audio;%BitRate%').strip(),
            duration=mediainfo(inform='Audio;%Duration%').strip(),
            size=mediainfo(inform='Audio;%StreamSize%').strip(),
            format=mediainfo(inform='Audio;%Format%').strip(),
        )
    )


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
    out_file_name = '%s.mp4' % (info['file_name'])
    sys.stderr.write('Encoding %s -> %s\n' % (file, out_file_name))
    sys.stdout.write('Encoding %s -> %s\n' % (file, out_file_name))
    if method == '1pass':
        opts = input_ops + video_opts + audio_opts + [
            '-threads', '2',
            '-y',
            '%s/%s' % (info['dir'], out_file_name),
        ]
        progress = EncodingProgress('Pass 1 of 1:', info['video']['frame_count'])
        p = sh.ffmpeg(
            *opts,
            _err=progress.process_ffmpeg_line,
            _err_bufsize=256
        )
        p.wait()
        progress.finish()
    elif method == '2pass':
        pass1_progress = EncodingProgress('Pass 1 of 2: ', info['video']['frame_count'])
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
    filename = unicode(args.file.strip(), encoding='UTF-8')
    info = get_media_info(filename)
    convert(info, filename)

