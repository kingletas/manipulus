<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Console\Command;

use Magento\Framework\App\Filesystem\DirectoryList;
use Magento\Framework\Filesystem;
use Manipulus\Bundles\Model\DeployedBundles;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * Reports the bundles deployed under each theme, so a release can be checked.
 */
class ShowBundlesCommand extends Command
{
    /**
     * The command owns its own name: a rename would break every pipeline that calls it.
     */
    public const NAME = 'manipulus:bundles:show';

    public function __construct(
        private readonly Filesystem $filesystem,
        ?string $name = null
    ) {
        parent::__construct($name);
    }

    protected function configure(): void
    {
        $this->setName(self::NAME);
        $this->setDescription('List the deployed manipulus bundles and their sizes');
        parent::configure();
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $static = $this->filesystem->getDirectoryRead(DirectoryList::STATIC_VIEW);
        $found = $static->search('*/*/*/*/' . DeployedBundles::DIRECTORY . '/bundle-*.js');

        if ($found === []) {
            $output->writeln('<comment>No bundles are deployed. Run manipulus build.</comment>');
            return Command::SUCCESS;
        }

        $total = 0;
        foreach ($found as $path) {
            $bytes = $static->stat($path)['size'] ?? 0;
            $total += $bytes;
            $output->writeln(sprintf('  %8.0f kB  %s', $bytes / 1024, $path));
        }
        $output->writeln(sprintf('<info>%d bundle(s), %.0f kB</info>', count($found), $total / 1024));
        return Command::SUCCESS;
    }
}
