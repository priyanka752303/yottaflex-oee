PY ?= python3

.PHONY: starter full test repro repro-full docs sample clean

starter:        ## generate + calculate + validate + evaluate + export the starter dataset
	$(PY) -m oee run --scale starter

full:           ## full dataset: 100k state events, 500k count + inspection records (~1 min)
	$(PY) -m oee run --scale full

test:
	$(PY) -m unittest discover -s tests -v

repro:          ## same seed twice -> identical checksums; seed+1 -> different
	$(PY) -m oee repro --scale starter

repro-full:
	$(PY) -m oee repro --scale full

docs:           ## regenerate docs/DATA_DICTIONARY.md, docs/ERD.md, docs/schema.sql from oee/schema.py
	$(PY) -m oee docs

sample: starter ## refresh the committed starter sample (everything except the SQLite binary)
	rm -rf sample_data/starter && mkdir -p sample_data
	rsync -a --exclude '*.sqlite' out/starter/ sample_data/starter/

clean:
	rm -rf out
