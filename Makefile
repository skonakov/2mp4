pep8:
	pep8 src

pyflakes:
	pyflakes src

lint: pep8 pyflakes

travistest:
	python --version

	python setup.py install
	2mp4 -v

travis:
	pip install -q pep8
	#make pep8

	pip install -q pyflakes
	make pyflakes

	make travistest


.PHONY: pep8 pyflakes lint travistest travis
