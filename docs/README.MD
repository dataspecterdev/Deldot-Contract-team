## Where to write the documentation

```text
docs/source/index.rst
```

You can add further pages as a new file

```text
docs/source/setup.rst
docs/source/usage.rst
```

## Building the documentation
```
pip install -r requirements.txt 
cd docs
make html
```

Then open the file in a browser to view the page locally
```
docs/build/html/index.html
```
You can also use GitHub Actions to deploy the page in GitHub
