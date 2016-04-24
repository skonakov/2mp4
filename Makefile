pep8:
	pep8 py2mp4

pyflakes:
	pyflakes py2mp4

lint: pep8 pyflakes

travistest: clean wheel
	python --version

	cd dist && pip install *.whl
	2mp4 -v

dist:
	python setup.py sdist

wheel:
	python setup.py bdist_wheel

clean:
	rm -f dist/*

travis:
	pip install -q pep8
	#make pep8

	pip install -q pyflakes
	make pyflakes

	pip install -q wheel
	make travistest


.PHONY: pep8 pyflakes lint travistest travis dist wheel clean

