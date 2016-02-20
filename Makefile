
install:
	mkdir -p /etc/cowtv
	cp config/* /etc/cowtv/
	cp cowtv.py /usr/local/bin/cowtv
	chmod +x /usr/local/bin/cowtv
	cp config/supervisor.conf /etc/supervisor/conf.d/cowtv.conf
