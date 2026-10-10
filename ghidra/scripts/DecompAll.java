// Decompile every function to <outdir>/<8-hex-entry>.c ; args: outdir [minAddrHex maxAddrHex]
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class DecompAll extends GhidraScript {
    public void run() throws Exception {
        String[] a = getScriptArgs();
        File out = new File(a[0]); out.mkdirs();
        long lo = a.length > 1 ? Long.parseLong(a[1], 16) : 0, hi = a.length > 2 ? Long.parseLong(a[2], 16) : Long.MAX_VALUE;
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        PrintWriter idx = new PrintWriter(new FileWriter(new File(out, "_index.txt")));
        int n = 0;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            long e = f.getEntryPoint().getOffset();
            if (e < lo || e > hi) continue;
            idx.println(String.format("%08x %d %s", e, f.getBody().getNumAddresses(), f.getName()));
            DecompileResults r = d.decompileFunction(f, 60, monitor);
            if (r != null && r.decompileCompleted()) {
                PrintWriter w = new PrintWriter(new FileWriter(new File(out, String.format("%08x.c", e))));
                w.print(r.getDecompiledFunction().getC()); w.close();
            }
            if (++n % 2000 == 0) println("decompiled " + n);
        }
        idx.close();
        println("done " + n);
    }
}
