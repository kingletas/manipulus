<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Model;

use Magento\Framework\App\Filesystem\DirectoryList;
use Magento\Framework\Filesystem;
use Magento\Framework\Serialize\Serializer\Json;

/**
 * Recomputes the subresource integrity hashes Magento records for deployed static files.
 */
class IntegrityHashes
{
    /**
     * Magento writes one hash file per area, at the root of that area's static directory.
     */
    private const HASH_FILE = 'sri-hashes.json';

    private const ALGORITHM = 'sha256';

    public function __construct(
        private readonly Filesystem $filesystem,
        private readonly Json $json
    ) {
    }

    /**
     * Bring every recorded hash back into step with the file it describes.
     *
     * @return array<string, string[]> the keys refreshed and the keys whose file is gone,
     *                                 under 'refreshed' and 'missing'
     */
    public function refresh(bool $dryRun = false): array
    {
        $static = $this->filesystem->getDirectoryWrite(DirectoryList::STATIC_VIEW);
        $refreshed = [];
        $missing = [];

        foreach ($this->hashFiles($static) as $hashFile) {
            // The area is the directory the hash file sits in, and the path is
            // always relative to the static root, so this is string work rather
            // than a filesystem question.
            $area = (string) strstr($hashFile, '/', true);
            $recorded = $this->json->unserialize($static->readFile($hashFile));
            if (!is_array($recorded)) {
                continue;
            }

            $changed = false;
            foreach (array_keys($recorded) as $key) {
                $target = $this->resolve($area, (string)$key);
                if (!$static->isExist($target)) {
                    $missing[] = (string)$key;
                    continue;
                }
                $actual = $this->hash($static->readFile($target));
                if ($recorded[$key] !== $actual) {
                    $recorded[$key] = $actual;
                    $refreshed[] = (string)$key;
                    $changed = true;
                }
            }

            if ($changed && !$dryRun) {
                $static->writeFile($hashFile, $this->json->serialize($recorded));
            }
        }

        return ['refreshed' => $refreshed, 'missing' => $missing];
    }

    /**
     * The recorded key is area-relative, and the hash file sits in that area's directory.
     */
    private function resolve(string $area, string $key): string
    {
        $prefix = $area . '/';
        return str_starts_with($key, $prefix) ? $key : $prefix . $key;
    }

    private function hash(string $contents): string
    {
        return self::ALGORITHM . '-' . base64_encode(hash(self::ALGORITHM, $contents, true));
    }

    /**
     * @return string[]
     */
    private function hashFiles(\Magento\Framework\Filesystem\Directory\WriteInterface $static): array
    {
        $found = [];
        foreach ($static->search('*/' . self::HASH_FILE) as $path) {
            $found[] = $path;
        }
        return $found;
    }
}
