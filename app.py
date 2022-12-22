import yaml
import os
from dictdiffer import diff
import sys
import re
from configparser import ConfigParser
from pathlib import Path


parser = ConfigParser()
parser.read(Path('init.ini').absolute())


class Args:
    dryrun = parser['folders']['dryrun']
    backup = parser['folders']['backup']
    diff = parser['folders']['diff']
    save_to_files = int(parser['output_format']['save_to_files'])
    is_colored_output = int(parser['output_format']['is_colored_output'])
    is_not_html = int(parser['output_format']['is_not_html'])

    
ignored_list = ["metadata.selfLink", "metadata.resourceVersion", "metadata.uid", "metadata.creationTimestamp",
                "metadata.managedFields", "status", "lifecycle", "args", "apiVersion", "terminationMessagePath",
                "terminationMessagePolicy", "scheme", "spec.template.spec.restartPolicy", "dnsPolicy", "schedulerName",
                "spec.clusterIP", "spec.sessionAffinity", "spec.template.spec.dnsPolicy",
                "metadata.annotations.'meta.helm.sh/release-name'",
                "metadata.annotations.meta.helm.sh/release-namespace",
                "metadata.labels.app.kubernetes.io/managed-by"]

if Args.is_not_html == 1:
    class FontColor:
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
else:
    class FontColor:
        OKGREEN = '<pre style="color:green;">'
        WARNING = '<pre style="color:orange;">'
        FAIL = '<pre style="color:red;">'
        ENDC = '</pre>'


def dict_print(dictionary, color, color_end, indent):
    if isinstance(dictionary, dict):
        for key_in_dict, value_in_dict in dictionary.items():
            if isinstance(value_in_dict, dict):
                print(f"{color * Args.is_colored_output}{indent * '  '}{key_in_dict}:{color_end * Args.is_colored_output}")
                indent += 1
                dict_print(value_in_dict, color, color_end, indent)
                indent -= 1
            else:
                if isinstance(value_in_dict, str) or isinstance(value_in_dict, int) or isinstance(value_in_dict, bool):
                    print(f"{color * Args.is_colored_output}{indent * '  '}{key_in_dict}: {value_in_dict}{color_end * Args.is_colored_output}")
                elif isinstance(value_in_dict, list):
                    print(f"{color * Args.is_colored_output}{indent * '  '}{key_in_dict}:{color_end * Args.is_colored_output}")
                    for elem in value_in_dict:
                        print(f"{color * Args.is_colored_output}{indent * '  '}-{color_end * Args.is_colored_output}")
                        dict_print(elem, color, color_end, indent+1)
    else:
        print("БЫЛ НЕ СЛОВАРЬ, строка 59 в исходном коде")


def pretty_printer_value(separate_symbol, differed_value_list, color, color_end, indent):
    last_element = differed_value_list[-1]
    for elem in differed_value_list:
        # Если это просто строка, то печатаем ее, и не добавляем перенос строки, поскольку дальше два варианта:
        # 1) Следом будет тоже строка, и тогда это ключ: значение - должны быть на одной строке
        # 2) Следом будет словарь, и тогда далее будет блок переменных
        if isinstance(elem, str) or isinstance(elem, int) or isinstance(elem, bool) or elem is None:
            if elem != last_element:
                print(f"{color * Args.is_colored_output}{indent * '  '}{str(elem)}{color_end * Args.is_colored_output * Args.is_not_html}{separate_symbol}", end='')
            else:
                print(f"{color * Args.is_colored_output * Args.is_not_html}{str(elem)}{color_end * Args.is_colored_output}")
            indent += 1
        elif isinstance(elem, list):
            for list_item in elem:
                print(f"{color_end * Args.is_colored_output * (1 - Args.is_not_html)}\n{color * Args.is_colored_output}{indent * '  '}-{color_end * Args.is_colored_output}")
                print(f"{color * Args.is_colored_output}{(indent + 1) * '  '}{str(list_item)}{color_end * Args.is_colored_output}")
        # Со словарем может быть несколько ситуаций:
        # 1) {'meta.helm.sh/release-name': 'cs-organization', 'meta.helm.sh/release-namespace': 'ps1-genr01-csoc-prod'}
        # просто ключ-значение
        # 2) {'hikari': {'connectionTimeout': 30000, 'idleTimeout': 30000, 'maxLifetime': 2000000, 'maximumPoolSize': 5, 'minimumIdle': 7, 'poolName': 'csOrganizationConnectionPool'}}
        # вложенный словарь
        # 3) {'clients': {'enabled': False, 'v2': {'connection': {'connection-request-timeout': 60000, 'connection-timeout': 60000, 'max-connection': 30, 'max-connection-per-route': 30, 'read-timeout': 60000}, 'create-url': 'http://cross-ref-organization-nossl:10028/api/cross/csrf/v2/crossreferences', 'delete-url': 'http://cross-ref-organization-nossl:10028/api/cross/csrf/v2/crossreferences', 'enabled': True, 'get-url': 'http://cross-ref-organization-nossl:10028/api/cross/csrf/v2/crossreferences/get', 'logging': {'log-request': True, 'log-request-body': True, 'log-response': True, 'log-response-body': True, 'masking': False}, 'security': {'key-store': None, 'mode': 'NONE', 'trust-store': None}}}}
        # несколько вложенных словарей
        # Поэтому парсить их нужно рекурсивно
        elif isinstance(elem, dict):
            print(f"{color_end * Args.is_colored_output * (1 - Args.is_not_html)}")
            dict_print(elem, color, color_end, indent)


def pretty_printer_path(path_to_diff, diff_block):
    indent = 0
    separate_symbol = ':'
    if path_to_diff[0] == 'add':
        path_to_diff[0] = 'Добавлен блок'
        color = FontColor.OKGREEN
        color_end = FontColor.ENDC
    elif path_to_diff[0] == 'remove':
        path_to_diff[0] = 'Удален блок'
        color = FontColor.FAIL
        color_end = FontColor.ENDC
    elif path_to_diff[0] == 'change':
        path_to_diff[0] = 'Изменилось значение'
        separate_symbol = " -> "
        color = FontColor.WARNING
        color_end = FontColor.ENDC
    else:
        color = FontColor.WARNING
        color_end = FontColor.ENDC
        path_to_diff[0] = 'Неизвестное изменение'
    # Если формат вывода - html, то для изменившихся значений строится таблица
    # Поэтому это вынесено в отдельный блок.
    # Если же формат вывода не html, то фукнция обработки общая
    if path_to_diff[0] != 'Изменилось значение' or Args.is_not_html == 1:
        if Args.is_not_html == 0:
            print(f'<p style="border:3px #A9A9A9  solid;">')
        # Выводим тип изменения
        print(f'\n{color * Args.is_colored_output}{path_to_diff[0]}:{color_end * Args.is_colored_output}')
        # Выводим путь к измененному блоку
        for variable_index in range(1, len(path_to_diff)):
            print(f"{color * Args.is_colored_output}{'  ' * indent}{path_to_diff[variable_index]}:{color_end * Args.is_colored_output}")
            indent += 1
        pretty_printer_value(separate_symbol, diff_block, color, color_end, indent)
    else:
        print('<p style="border:3px #A9A9A9  solid;">')
        print('<pre style="color:orange;">Изменилось значение:</pre>\n<table style="width:100%">\n<tr>\n\
        <th>Было</th>\n\
        <th>Стало</th>\n</tr>')
        print('<tr>')
        for loop in range(0, 2):
            print('<td>')
            indent = 0
            for variable_index in range(1, len(path_to_diff)):
                print(
                    f"<pre>{'  ' * indent}{path_to_diff[variable_index]}:</pre>")
                indent += 1
            print('</td>')
        print('</tr>')
        print('<tr>')
        print('<td>')
        if isinstance(diff_block[0], dict):
            dict_print(diff_block[0], FontColor.FAIL, FontColor.ENDC, indent)
        else:
            print(f'{FontColor.FAIL}{"  " * indent}{diff_block[0]}{FontColor.ENDC}')
        print('</td>')
        print('<td>')
        if isinstance(diff_block[1], dict):
            dict_print(diff_block[1], FontColor.OKGREEN, FontColor.ENDC, indent)
        else:
            print(f'{FontColor.OKGREEN}{"  " * indent}{diff_block[1]}{FontColor.ENDC}')
        print('</td>')
        print('</tr>')
        print('</table>')


def cycle_file_differ(backup_location, dryrun_location, diff_location):
    backup_files = []
    for file in os.listdir(backup_location):
        if file.endswith(".yaml"):
            backup_files.append(file)
    dryrun_files = []
    for file in os.listdir(dryrun_location):
        if file.endswith(".yaml") and not file.startswith("dry"):
            dryrun_files.append(file)
    for backup_file in dryrun_files:
        if backup_file in backup_files:
            with open(f"{dryrun_location}/{backup_file}", "r") as stream:
                try:
                    dry_yaml = yaml.unsafe_load(stream)
                except yaml.YAMLError as exc:
                    print(exc)

            with open(f"{backup_location}/{backup_file}", "r") as stream:
                try:
                    temp_backup = stream.read()
                    temp_backup = temp_backup.replace("application-secure.yml: |", "application-secure.yml:")
                    temp_backup = temp_backup.replace("application.yml: |", "application.yml:")
                    backup_yaml = yaml.unsafe_load(temp_backup)
                except yaml.YAMLError as exc:
                    print(exc)
            original_stdout = sys.stdout
            if Args.save_to_files == 1:
                sys.stdout = open(f"{diff_location}/{backup_file}.html", 'w')
            if Args.is_not_html == 0:
                print("<!DOCTYPE html>\n<html>\n<meta charset='utf-8'>")
                print("<style>table, th, td {  border:1px solid black;}</style>")
            clean_yaml_diff = diff(backup_yaml, dry_yaml, ignore=ignored_list, expand=True)
            # Пример структуры изменений
            # ('remove', 'metadata.labels', [('app.kubernetes.io/managed-by', 'Helm')])
            # ('remove', 'metadata', [('annotations', {'meta.helm.sh/release-name': 'cs-organization', 'meta.helm.sh/release-namespace': 'ps1-genr01-csoc-prod'})])
            for elem in list(clean_yaml_diff):
                # Вывод типа изменения
                path_to_changed_block = [elem[0]]
                # Путь к переменным может быть либо строкой, либо массивом:
                # ['data', 'application.yml', 'server']
                # metadata.annotations
                # Код ниже приводит строки тоже к массиву
                if isinstance(elem[1], str):
                    a = elem[1].split('.')
                    path_to_changed_block.extend(a)
                else:
                    path_to_changed_block.extend(elem[1])
                # Сам измененный элемент тоже может быть простой или сложной структурой:
                # [('evict-on-create-enabled', True)]
                # [('csrf', {'clients': {'enabled': False, 'v2': {'connection': {'connection-request-timeout': 60000, 'connection-timeout': 60000, 'max-connection': 30, 'max-connection-per-route': 30, 'read-timeout': 60000}, 'create-url': 'http://cross-ref-organization-nossl:10028/api/cross/csrf/v2/crossreferences', 'delete-url': 'http://cross-ref-organization-nossl:10028/api/cross/csrf/v2/crossreferences', 'enabled': True, 'get-url': 'http://cross-ref-organization-nossl:10028/api/cross/csrf/v2/crossreferences/get', 'logging': {'log-request': True, 'log-request-body': True, 'log-response': True, 'log-response-body': True, 'masking': False}, 'security': {'key-store': None, 'mode': 'NONE', 'trust-store': None}}}})]
                # [('etalons-search', {'enable-get-omni-cross-refs': False})]
                if elem[0] != 'change':
                    changed_block = list(elem[2][0])
                else:
                    changed_block = list(elem[2])
                pretty_printer_path(path_to_changed_block, changed_block)
            if Args.is_not_html == 0:
                print("\n</html>")
            sys.stdout = original_stdout
        else:
            print(f"Файл {backup_file} отсутсвтует в backup")


if __name__ == "__main__":

    dryrun_file = 'dry_run.yaml'
    for file in os.listdir(Args.dryrun):
        if file.endswith(".yaml") and file.startswith("dry"):
            dryrun_file = file
            break
    else:
        print("Dryrun файл не найден")
        exit(-1)

    with open(f"{Args.dryrun}/{dryrun_file}", "r") as stream:
        dryrun = stream.read()
        manifest_starts = dryrun.find("MANIFEST")
        dryrun = dryrun[manifest_starts + 13::]
        dryrun = dryrun.replace("application.yml: |", "application.yml:")
        dryrun = re.sub(r"#.+\n", "", dryrun)
        dryrun = dryrun.split('---')

    for elem in dryrun:
        tmp_manifest = yaml.unsafe_load(elem)
        original_stdout = sys.stdout
        with open(f"dryrun/{tmp_manifest['kind'].lower()}-{tmp_manifest['metadata']['name']}.yaml", 'w') as out_file:
            sys.stdout = out_file  # Change the standard output to the file we created.
            print(yaml.dump(tmp_manifest))
            sys.stdout = original_stdout

    cycle_file_differ(Args.backup, Args.dryrun, Args.diff)
