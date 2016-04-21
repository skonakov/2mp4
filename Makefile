pep8:
	pep8 2mp4

pyflakes:
	pyflakes 2mp4

lint: pep8 pyflakes

travistest:
	python --version

	python setup.py install
	2mp4 -v

dist:
	python setup.py sdist

travis:
	pip install -q pep8
	#make pep8

	pip install -q pyflakes
	make pyflakes

	make travistest


.PHONY: pep8 pyflakes lint travistest travis dist
