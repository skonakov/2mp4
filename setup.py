import os

from setuptools import setup, find_packages


classifiers = """\
Intended Audience :: Developers
License :: OSI Approved :: MIT License
Programming Language :: Python
Topic :: Software Development :: Compilers
Operating System :: Unix
"""

setup(
    name='2mp4',
    version='0.0.1',
    url='https://github.com/skonakov/2mp4.git',
    license='MIT',
    description='2mp4 - TBD',
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
