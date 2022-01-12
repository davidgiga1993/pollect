import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='pollect',
    version='1.1.2',
    author='davidgiga1993',
    author_email='david@dev-core.org',
    description='Metrics collection daemon (similar to collectd)',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/davidgiga1993/pollect',
    packages=setuptools.find_packages(),
    python_requires='>3.6',
    install_requires=['schedule'],
    entry_points={
        'console_scripts': ['pollect=pollect.Pollect:main'],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
