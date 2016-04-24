import subprocess
import sys

from collections import namedtuple
from setuptools import setup


classifiers = """\
Intended Audience :: End Users/Desktop
License :: OSI Approved :: MIT License
Programming Language :: Python
Topic :: Multimedia :: Video :: Conversion
Operating System :: Unix
"""

try:
    p = subprocess.Popen(
        ['git', 'describe', '--tags'],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=False
    )
    p.wait()
except:
    p = namedtuple('Process', 'returncode')(1)

if p.returncode == 0:
    version = p.communicate()[0].strip().decode()
    with open('.version', 'w+') as version_file:
        version_file.write(version)
else:
    with open('.version', 'r') as version_file:
        version = version_file.readline().strip()

requirements = ['sh', 'progressbar2', 'pymediainfo']
if sys.version_info[0] == 3:
    requirements.extend(['beautifulsoup4', 'lxml'])


setup(
    name='2mp4',
    version=version,
    url='https://github.com/skonakov/2mp4.git',
    download_url='https://github.com/skonakov/2mp4/tarball/' + version,
    license='MIT',
    description='Simple utility to convert your video files into mp4s.',
    author='Sergey Konakov',
    author_email='skonakov@gmail.com',
    packages=['py2mp4'],
    package_dir={'py2mp4': 'py2mp4'},
    package_data={'py2mp4': ['../.version']},
    install_requires=requirements,
    zip_safe=False,
    entry_points="""\
    [console_scripts]
    2mp4 = py2mp4:main
    """,
    classifiers=filter(None, classifiers.split('\n')),
    #long_description=read('README.rst') + '\n\n' + read('CHANGES'),
    #extras_require={'test': []}
)
