<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 * @license   MIT https://opensource.org/licenses/MIT
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Test\Unit\Model;

use Manipulus\Bundles\Model\CommandLine;
use PHPUnit\Framework\TestCase;

class CommandLineTest extends TestCase
{
    public function testPhpUnitRunsOnTheCommandLineAsAStaticDeployDoes(): void
    {
        $this->assertTrue((new CommandLine())->isCurrent());
    }
}
