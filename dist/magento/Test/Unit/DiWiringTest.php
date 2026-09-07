<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 * @license   MIT https://opensource.org/licenses/MIT
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Test\Unit;

use PHPUnit\Framework\TestCase;

/**
 * The XML in etc/ against the code it names.
 */
class DiWiringTest extends TestCase
{
    // A di.xml naming a renamed class does not fail at compile time. It fails
    // when something first asks for it, which is usually a command that has
    // quietly stopped being registered.

    private function moduleDir(): string
    {
        return dirname(__DIR__, 2);
    }

    private function di(): \SimpleXMLElement
    {
        $xml = simplexml_load_file($this->moduleDir() . '/etc/di.xml');
        $this->assertNotFalse($xml, 'etc/di.xml is not parsable XML');

        return $xml;
    }

    public function testEveryClassNamedInDiXmlExists(): void
    {
        $named = [];

        foreach ($this->di()->xpath('//item[@xsi:type="object"]') ?: [] as $item) {
            $named[] = trim((string) $item);
        }

        foreach ($this->di()->xpath('//type/@name') ?: [] as $name) {
            $named[] = trim((string) $name);
        }

        $this->assertNotEmpty($named, 'di.xml names no classes at all, which cannot be right');

        foreach (array_unique($named) as $class) {
            $this->assertTrue(
                class_exists($class) || interface_exists($class),
                "di.xml names {$class}, which does not exist"
            );
        }
    }

    public function testTheCommandsAreRegisteredWithTheCommandList(): void
    {
        $registered = [];

        $commandList = '//type[@name="Magento\Framework\Console\CommandListInterface"]//item';

        foreach ($this->di()->xpath($commandList) ?: [] as $item) {
            $registered[] = trim((string) $item);
        }

        $this->assertContains(\Manipulus\Bundles\Console\Command\RefreshIntegrityCommand::class, $registered);
        $this->assertContains(\Manipulus\Bundles\Console\Command\ShowBundlesCommand::class, $registered);
    }

    public function testTheModuleDeclaresItSequencesAfterWhatItDependsOn(): void
    {
        $module = simplexml_load_file($this->moduleDir() . '/etc/module.xml');
        $this->assertNotFalse($module);

        $sequenced = [];

        foreach ($module->xpath('//sequence/module/@name') ?: [] as $name) {
            $sequenced[] = (string) $name;
        }

        // RequireJs merges the config this module contributes; Csp records the
        // integrity hashes the commands put back in step.
        $this->assertContains('Magento_RequireJs', $sequenced);
        $this->assertContains('Magento_Csp', $sequenced);
    }
}
