import * as vscode from "vscode";
import { spawn } from "child_process";

export function activate(context: vscode.ExtensionContext) {
  context.subscriptions.push(
    vscode.commands.registerCommand("demodsl.run", () =>
      runDemodsl("run", "Run Demo")
    ),
    vscode.commands.registerCommand("demodsl.validate", () =>
      runDemodsl("validate", "Validate Config")
    ),
    vscode.commands.registerCommand("demodsl.init", () =>
      runDemodsl("init", "Init Config")
    )
  );
}

async function runDemodsl(command: string, label: string) {
  const config = vscode.workspace.getConfiguration("demodsl");
  const bin = config.get<string>("pythonPath", "demodsl");
  const outputDir = config.get<string>("outputDir", "output");
  const renderer = config.get<string>("renderer", "moviepy");

  let args: string[];

  if (command === "init") {
    args = ["init"];
  } else {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showErrorMessage("Open a YAML config file first.");
      return;
    }
    const filePath = editor.document.fileName;
    if (!filePath.endsWith(".yaml") && !filePath.endsWith(".yml")) {
      vscode.window.showWarningMessage("Active file is not a YAML file.");
      return;
    }
    args = [command, filePath];
    if (command === "run") {
      args.push("--output-dir", outputDir, "--renderer", renderer);
    }
  }

  const terminal = vscode.window.createTerminal(`DemoDSL: ${label}`);
  terminal.show();
  terminal.sendText(`${bin} ${args.join(" ")}`);
}

export function deactivate() {}
