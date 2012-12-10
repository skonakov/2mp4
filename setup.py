import subprocess

from setuptools import setup, find_packages


classifiers = """\
Intended Audience :: End Users/Desktop
License :: OSI Approved :: MIT License
Programming Language :: Python
Topic :: Multimedia :: Video :: Conversion
Operating System :: Unix
"""


try:
    version = subprocess.Popen(
        ['git', 'describe', '--tags'],
        stdout=subprocess.PIPE
    ).communicate()[0].strip()
    with open('.version', 'w') as version_file:
        version_file.write(version)
except:
    with open('.version', 'r') as version_file:
        version = version_file.readline().strip()


setup(
    name='2mp4',
    version=version,
    url='https://github.com/skonakov/2mp4.git',
    download_url='https://github.com/skonakov/2mp4/tarball/' + version,
    license='MIT',
    description='Simple utility to convert your video files into mp4s.',
    author='Sergey Konakov',
    author_email='skonakov@gmail.com',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    install_requires=['sh', 'progressbar', 'pymediainfo'],
    zip_safe=False,
    entry_points="""\
    [console_scripts]
    2mp4 = 2mp4.2mp4:main
    """,
    classifiers=filter(None, classifiers.split('\n')),
    #long_description=read('README.rst') + '\n\n' + read('CHANGES'),
    #extras_require={'test': []}
)
