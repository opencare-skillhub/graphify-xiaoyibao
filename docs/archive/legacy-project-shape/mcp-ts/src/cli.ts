type CommandNode = {
  name(): string
}

class SimpleCommand {
  public readonly commands: CommandNode[] = []

  constructor(private readonly commandName: string) {}

  name(): string {
    return this.commandName
  }

  command(name: string): this {
    this.commands.push({
      name: () => name,
    })
    return this
  }

  parse(argv: string[]): void {
    const [subcommand, target] = argv
    if (subcommand === 'scan') {
      console.log(`scan ${target ?? ''}`.trim())
      return
    }
    if (subcommand === 'report') {
      console.log('report')
      return
    }
    if (subcommand === 'serve') {
      console.log('serve')
      return
    }
    console.log(this.commandName)
  }
}

export function buildCommand(): SimpleCommand {
  return new SimpleCommand('xyb')
    .command('scan')
    .command('report')
    .command('serve')
}

if (import.meta.url === new URL(process.argv[1] ?? '', 'file://').href) {
  buildCommand().parse(process.argv.slice(2))
}
