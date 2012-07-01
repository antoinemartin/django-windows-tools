@echo off
echo "Creating Django Windows service"

python DjangoService.py --startup auto install
python DjangoService.py start