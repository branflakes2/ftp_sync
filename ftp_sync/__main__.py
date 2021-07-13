import anyconfig
import click
import logging

from . import FTP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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

@main.command()
@click.pass_context
def sync_all(ctx):
    config = ctx.parent.config
    if 'port' not in config:
        config['port'] = 21
    helper = FTP.FTPHelper(hostname=config['hostname'], port=config['port'])
    sync = FTP.FTPSync(helper)
    for s in config.get('sync'):
        logger.info(f"sync: {s}")
        sync.sync(**s)

if __name__ == "__main__":
    main()
