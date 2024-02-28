from setuptools import setup


__version__ = '24.02'


with open('README.md') as f:
    long_description = f.read()


setup(name='galahad',
      packages=['galahad'],
      version=__version__,
      description='Connect to the Galaxy platform within Jupyter notebooks',
      long_description=long_description,
      long_description_content_type="text/markdown",
      license='BSD',
      author='Thorin Tabor',
      author_email='tmtabor@cloud.ucsd.edu',
      url='https://github.com/g2nb/galahad',
      download_url='https://github.com/g2nb/galahad/archive/' + __version__ + '.tar.gz',
      keywords=['galaxy', 'genomics', 'bioinformatics', 'ipython', 'jupyter'],
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: Science/Research',
          'Intended Audience :: Developers',
          'Topic :: Scientific/Engineering :: Bio-Informatics',
          'License :: OSI Approved :: BSD License',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Programming Language :: Python :: 3.11',
          'Framework :: Jupyter',
      ],
      install_requires=[
          'bioblend',
          'nbtools>=23.4',
          'jupyterlab>=3.6,<4',
          'ipywidgets>=8.0.0',
          'pandas',
      ],
      data_files=[("share/jupyter/nbtools", ["nbtools/galahad.json"])],
      normalize_version=False,
      )
