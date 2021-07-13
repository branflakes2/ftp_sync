import anyconfig
import click
import logging

from . import FTP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

patcher_dict = {
    "desmume": FTP.DESMumePatcher,
}

def _build_patcher(d):
    if "options" in d:
        options = d['options']
    else:
        options = {}
    return patcher_dict[d['name']](**options)

def _get_paths(d):
    return {'local_path': d['local_path'], 'remote_path': d['remote_path']}

def _parse_pair_to_kwargs(d):
    kwargs = {}
    if 'patcher' in d:
        kwargs['patcher'] = _build_patcher(d['patcher'])
    kwargs.update(_get_paths(d))
    return kwargs

@click.group()
@click.option('-c', '--config-file', type=str, required=True)
@click.option('-d', '--debug', is_flag=True)
@click.pass_context
def main(ctx, config_file, debug):
    if debug:
        logging.info("Debug mode on.")
        logger.setLevel(logging.DEBUG)
        FTP.logger.setLevel(logging.DEBUG)
        logging.basicConfig(level=logging.DEBUG)
    ctx.config = anyconfig.load(config_file)

@main.command(help="Automatically sync a specified sync pair.")
@click.option('-n', '--name', type=str, required=True, help="Sync pair name")
@click.pass_context
def sync(ctx, name):
    config = ctx.parent.config
    if 'port' not in config:
        config['port'] = 21
    helper = FTP.FTPHelper(hostname=config['hostname'], port=config['port'])
    sync = FTP.FTPSync(helper)
    s = config.get('sync').get(name)
    if s:
        logger.info(f"sync: {name}")
        sync.sync(**_parse_pair_to_kwargs(s))
    else:
        logger.warning(f"Not syncing: no sync pair {name}")

@main.command(help="Automatically sync all sync pairs.")
@click.pass_context
def sync_all(ctx):
    config = ctx.parent.config
    if 'port' not in config:
        config['port'] = 21
    helper = FTP.FTPHelper(hostname=config['hostname'], port=config['port'])
    sync = FTP.FTPSync(helper)
    for s in config.get('sync'):
        logger.info(f"sync: {s}")
        s = config.get('sync')[s]
        sync.sync(**_parse_pair_to_kwargs(s))

@main.command(help="Sync all sync pairs local to remote.")
@click.pass_context
def sync_all_to(ctx):
    config = ctx.parent.config
    if 'port' not in config:
        config['port'] = 21
    helper = FTP.FTPHelper(hostname=config['hostname'], port=config['port'])
    sync = FTP.FTPSync(helper)
    for s in config.get('sync'):
        logger.info(f"sync: {s}")
        s = config.get('sync')[s]
        sync.sync_to(**_parse_pair_to_kwargs(s))

@main.command(help="Sync all sync pairs remote to local.")
@click.pass_context
def sync_all_from(ctx):
    config = ctx.parent.config
    if 'port' not in config:
        config['port'] = 21
    helper = FTP.FTPHelper(hostname=config['hostname'], port=config['port'])
    sync = FTP.FTPSync(helper)
    for s in config.get('sync'):
        logger.info(f"sync: {s}")
        s = config.get('sync')[s]
        sync.sync_from(**_parse_pair_to_kwargs(s))

@main.command(help="Sync a pair local to remote.")
@click.option('-n', '--name', type=str, required=True, help="Sync pair name")
@click.pass_context
def sync_to(ctx, name):
    config = ctx.parent.config
    if 'port' not in config:
        config['port'] = 21
    helper = FTP.FTPHelper(hostname=config['hostname'], port=config['port'])
    sync = FTP.FTPSync(helper)
    s = config.get('sync').get(name)
    if s:
        logger.info(f"sync: {s}")
        sync.sync_to(**_parse_pair_to_kwargs(s))
    else:
        logger.warning(f"Not syncing: no sync pair {name}")

@main.command(help="Sync a pair remote to local.")
@click.option('-n', '--name', type=str, required=True, help="Sync pair name")
@click.pass_context
def sync_from(ctx, name):
    config = ctx.parent.config
    if 'port' not in config:
        config['port'] = 21
    helper = FTP.FTPHelper(hostname=config['hostname'], port=config['port'])
    sync = FTP.FTPSync(helper)
    s = config.get('sync').get(name)
    if s:
        logger.info(f"sync: {s}")
        sync.sync_from(**_parse_pair_to_kwargs(s))
    else:
        logger.warning(f"Not syncing: no sync pair {name}")

if __name__ == "__main__":
    main()
