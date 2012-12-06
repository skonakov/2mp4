from setuptools import setup, find_packages


classifiers = """\
Intended Audience :: End Users/Desktop
License :: OSI Approved :: MIT License
Programming Language :: Python
Topic :: Multimedia :: Video :: Conversion
Operating System :: Unix
"""

setup(
    name='2mp4',
    version='0.0.4',
    url='https://github.com/skonakov/2mp4.git',
    download_url='https://github.com/skonakov/2mp4/tarball/0.0.4',
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
