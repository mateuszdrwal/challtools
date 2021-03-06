import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="challtools",  # Replace with your own username
    version="0.0.1",
    author="Mateusz Drwal",
    author_email="drwal.mateusz@gmail.com",
    description="A small example package",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mateuszdrwal/challtools",
    packages=setuptools.find_packages(),
    package_data={"": ["challenge.schema.json", "codes.yml"]},
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    entry_points={"console_scripts": ["challtools = challtools.cli:main"]},
    install_requires=[
        "PyYAML",
        "jsonschema",
        "docker",
        "requests",
    ],
)
