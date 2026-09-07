<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Console\Command;

use Manipulus\Bundles\Model\IntegrityHashes;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * Puts the recorded integrity hashes back in step with the files they describe.
 */
class RefreshIntegrityCommand extends Command
{
    /**
     * The command owns its own name: a rename would break every pipeline that calls it.
     */
    public const NAME = 'manipulus:integrity:refresh';

    private const DRY_RUN = 'dry-run';

    public function __construct(
        private readonly IntegrityHashes $hashes,
        ?string $name = null
    ) {
        parent::__construct($name);
    }

    protected function configure(): void
    {
        $this->setName(self::NAME);
        $this->setDescription('Recompute subresource integrity hashes for deployed static files');
        // Symfony's console reserves -n for --no-interaction, so this option has no shortcut.
        $this->addOption(self::DRY_RUN, null, InputOption::VALUE_NONE, 'Report without writing');
        parent::configure();
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $dryRun = (bool)$input->getOption(self::DRY_RUN);
        $result = $this->hashes->refresh($dryRun);
        $verb = $dryRun ? 'would refresh' : 'refreshed';
        $summary = $dryRun ? 'would be refreshed' : 'refreshed';

        foreach ($result['missing'] as $key) {
            $output->writeln("<comment>hashed but not deployed: {$key}</comment>");
        }
        foreach ($result['refreshed'] as $key) {
            $output->writeln("  {$verb} {$key}");
        }

        $count = count($result['refreshed']);
        if ($count === 0) {
            return Command::SUCCESS;
        }

        $output->writeln("<info>{$count} hash(es) {$summary}.</info>");
        return Command::SUCCESS;
    }
}
