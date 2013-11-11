
install:
	mkdir -p /etc/cowtv
	cp cowtv.yml /etc/cowtv/
	cp cowtv.py /usr/local/bin/cowtv
	chmod +x /usr/local/bin/cowtv
