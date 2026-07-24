type ToolCallRowProps = {
  toolCall: {
    name: string;
    inputs: Record<string, unknown>;
    outputs?: unknown;
    latencyMs: number;
  };
};

export function ToolCallRow({ toolCall }: ToolCallRowProps) {
  return (
    <details className="rounded-md border p-2 text-xs">
      <summary className="cursor-pointer font-mono font-medium">
        {toolCall.name}{" "}
        <span className="font-sans text-muted-foreground">
          ({toolCall.latencyMs}ms)
        </span>
      </summary>
      <div className="mt-2 space-y-2">
        <div>
          <p className="text-muted-foreground">Input</p>
          <pre className="overflow-x-auto rounded bg-muted p-2">
            {JSON.stringify(toolCall.inputs, null, 2)}
          </pre>
        </div>
        <div>
          <p className="text-muted-foreground">Output</p>
          <pre className="overflow-x-auto rounded bg-muted p-2">
            {JSON.stringify(toolCall.outputs, null, 2)}
          </pre>
        </div>
      </div>
    </details>
  );
}
