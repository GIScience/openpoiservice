import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="openpoiservice",
    version="0.1.7",
    author="Timothy Ellersiek",
    author_email="timothy@openrouteservice.org",
    description="POI service consuming OpenStreetMap data",
    keywords='OSM ORS openrouteservice openstreetmap POI points of interest',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/GIScience/openpoiservice",
    packages=setuptools.find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    project_urls={
        'Bug Reports': 'https://github.com/GIScience/openpoiservice/issues',
        'Source': 'https://github.com/GIScience/openpoiservice',
    },
)
