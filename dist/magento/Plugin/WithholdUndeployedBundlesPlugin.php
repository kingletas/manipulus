<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Plugin;

use Magento\Framework\RequireJs\Config\File\Collector\Aggregated;
use Magento\Framework\View\Asset\Repository;
use Magento\Framework\View\Design\ThemeInterface;
use Magento\Framework\View\File;
use Manipulus\Bundles\Model\CommandLine;
use Manipulus\Bundles\Model\DeployedBundles;

/**
 * Leaves this module's bundles map out of a merged requirejs-config.js when its bundles are not deployed.
 */
class WithholdUndeployedBundlesPlugin
{
    private const MODULE = 'Manipulus_Bundles';

    private const CONFIG_FILE = 'requirejs-config.js';

    public function __construct(
        private readonly DeployedBundles $deployedBundles,
        private readonly Repository $assetRepository,
        private readonly CommandLine $commandLine
    ) {
    }

    /**
     * Always kept on the command line, where a static deploy merges before `manipulus build` writes the bundles.
     *
     * @param File[] $files
     * @return File[]
     */
    public function afterGetFiles(Aggregated $subject, array $files, ThemeInterface $theme, string $filePath): array
    {
        if ($filePath !== self::CONFIG_FILE || $this->commandLine->isCurrent()) {
            return $files;
        }

        $staticPath = $this->assetRepository->getStaticViewFileContext()->getPath();

        return array_values(array_filter(
            $files,
            fn (File $file): bool => $file->getModule() !== self::MODULE
                || $this->deployedBundles->areDeployed($file->getFilename(), $staticPath)
        ));
    }
}
