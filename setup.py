import setuptools

with open("requirements.txt") as f:
    requirements = f.readlines()

setuptools.setup(
    name="ftp_sync",
    version="0.0.1",
    author="Brian Weber",
    author_email="brianweber11@gmail.com",
    description="Syncs specified files with an ftp server",
    packages=setuptools.find_packages(),
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
    python_requires='>=3.8',
)
