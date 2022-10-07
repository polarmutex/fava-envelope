install_reqs:
	pip install -r ./requirements.in
update_req_txt:
	pip freeze > requirements.txt
pre-commit:
	pre-commit run --all-files
