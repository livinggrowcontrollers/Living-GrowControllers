# Verbindlicher Refactor-Standard

Für dieses Projekt gilt bei Refactorings:

- Jede Klasse, Funktion und Verantwortung besitzt genau einen echten Implementierungsort.
- Alle Nutzer importieren diesen Ort direkt.
- Keine Import-Weiterleitungen, Re-Export-Fassaden, Alias-Module oder Lazy-Import-Ketten.
- Keine parallelen Alt- und Neumodule mit gleicher Bedeutung oder gleichem Namen.
- Paket-`__init__.py` werden nicht als Import-Abkürzung verwendet.
- Bei einer Verschiebung werden alle Importe angepasst und der alte Quellpfad anschließend entfernt.
- Rückwärtskompatible Wrapper werden nur nach ausdrücklicher Zustimmung angelegt. Wenn Kompatibilität technisch notwendig erscheint, wird das vor der Umsetzung erklärt.
- Ein Refactor ist erst abgeschlossen, wenn nach alten Pfaden, alten Symbolnamen und reinen Import-Modulen gesucht wurde und die relevanten Tests bestanden sind.

Ziel ist eine unmittelbar lesbare und manuell wartbare Architektur: kein Schild darf lediglich auf ein weiteres Schild verweisen.
