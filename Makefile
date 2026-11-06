.PHONY: build up down logs restart clean

build:
	cd atlasnew && docker-compose build

up:
	cd atlasnew && docker-compose up -d

down:
	cd atlasnew && docker-compose down

restart:
	cd atlasnew && docker-compose restart

logs:
	cd atlasnew && docker-compose logs -f

clean:
	cd atlasnew && docker-compose down -v
