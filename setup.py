import setuptools
from pathlib import Path

setuptools.setup(
    name="challtools",
    version="0.0.1",
    author="Mateusz Drwal",
    author_email="me@mateuszdrwal.com",
    description="A tool for managing CTF challenges and challenge repositories using the OpenChallSpec",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/mateuszdrwal/challtools",
    packages=setuptools.find_packages(),
    package_data={
        "challtools": ["challenge.schema.json", "codes.yml"]
        + [
            str(path.relative_to("challtools"))
            for path in Path("challtools/templates").rglob("*")
            if path.is_file()
        ]
    },
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
        "google-cloud-storage",
    ],
)
