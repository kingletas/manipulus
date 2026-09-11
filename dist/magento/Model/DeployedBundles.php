<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Model;

use Magento\Framework\App\Filesystem\DirectoryList;
use Magento\Framework\Filesystem;
use Magento\Framework\Filesystem\Directory\ReadInterface;
use Magento\Framework\Filesystem\Driver\File;
use Magento\Framework\Serialize\Serializer\Json;
use Magento\Framework\View\Asset\Minification;

/**
 * Says whether every bundle a requirejs-config.js names is deployed under one theme and locale.
 */
class DeployedBundles
{
    /**
     * The directory manipulus writes its bundles into, under each theme and locale.
     */
    public const DIRECTORY = 'manipulus';

    /**
     * The shape `manipulus build --module` writes: one `var config` holding a JSON object.
     */
    private const CONFIG_PATTERN = '/var\s+config\s*=\s*(\{.*\})\s*;?\s*$/s';

    /**
     * A bundle id that could point outside the bundle directory is refused rather than looked up.
     */
    private const BUNDLE_ID_PATTERN = '#^' . self::DIRECTORY . '/bundle-[A-Za-z0-9_-]+$#';

    public function __construct(
        private readonly Filesystem $filesystem,
        private readonly File $driver,
        private readonly Json $json,
        private readonly Minification $minification
    ) {
    }

    /**
     * True when every bundle the config file names is on disk under the static path, as RequireJS will request it.
     */
    public function areDeployed(string $configFile, string $staticPath): bool
    {
        $bundleIds = $this->bundleIds($this->driver->fileGetContents($configFile));
        if ($bundleIds === null) {
            return false;
        }

        $static = $this->filesystem->getDirectoryRead(DirectoryList::STATIC_VIEW);
        foreach ($bundleIds as $bundleId) {
            if (!$this->isDeployed($static, $staticPath . '/' . $bundleId)) {
                return false;
            }
        }

        return true;
    }

    /**
     * Minification changes the name RequireJS asks for, so the check follows it.
     */
    private function isDeployed(ReadInterface $static, string $bundle): bool
    {
        return $static->isFile($this->minification->addMinifiedSign($bundle . '.js'));
    }

    /**
     * @return string[]|null the bundle ids, or null when the file is not a map this module can vouch for
     */
    private function bundleIds(string $config): ?array
    {
        if (preg_match(self::CONFIG_PATTERN, $config, $match) !== 1) {
            return null;
        }

        try {
            $decoded = $this->json->unserialize($match[1]);
        } catch (\InvalidArgumentException) {
            return null;
        }

        if (!is_array($decoded) || !is_array($decoded['bundles'] ?? null)) {
            return null;
        }

        $bundleIds = array_map('strval', array_keys($decoded['bundles']));
        foreach ($bundleIds as $bundleId) {
            if (preg_match(self::BUNDLE_ID_PATTERN, $bundleId) !== 1) {
                return null;
            }
        }

        return $bundleIds;
    }
}
