@echo off
echo "Uninstalling Django Windows service"

python DjangoService.py stop
python DjangoService.py remove
