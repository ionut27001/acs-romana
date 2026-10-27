// Headless driver for AnvilToolkit (GUI-only tool): loads AnvilToolkit.dll and calls its forge/localization code.
//   anvilcli inspect [methods] [regex]   list types/methods
//   anvilcli list <forge> [regex]        list entries of a forge (index only, nothing extracted)
using System.IO;
using System.Reflection;
using System.Text.RegularExpressions;

const string AtkDir = @"D:\acs-ro\tools\AnvilToolkit";
const BindingFlags All = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;

AppDomain.CurrentDomain.AssemblyResolve += (_, e) =>
{
    var name = new AssemblyName(e.Name).Name + ".dll";
    foreach (var dir in new[] { AtkDir, Path.Combine(AtkDir, "Libs") })
    {
        var p = Path.Combine(dir, name);
        if (File.Exists(p)) return Assembly.LoadFrom(p);
    }
    return null;
};
var asm = Assembly.LoadFrom(Path.Combine(AtkDir, "AnvilToolkit.dll"));
Type T(string n) => asm.GetType(n, true);
object Get(object o, string member) => o.GetType().GetProperty(member, All)?.GetValue(o) ?? o.GetType().GetField(member, All)?.GetValue(o);

void Setup()
{
    // the toolkit loads Lists\<game>.gfl and its native DLLs (Oodle, DirectXTex) relative to the working directory;
    // without this it pops up "file list not found" / "DirectXTex DLL not found" dialogs
    Environment.CurrentDirectory = AtkDir;
    // load the toolkit's App.xaml resources (styles the forge code looks up) without showing any window
    if (System.Windows.Application.Current == null)
    {
        // relative pack URIs in App.xaml must resolve against AnvilToolkit.dll, not this exe
        // (the public setter refuses once WPF has defaulted it to the entry assembly, so set the backing field)
        typeof(System.Windows.Application).GetField("_resourceAssembly", All).SetValue(null, asm);
        var app = Activator.CreateInstance(T("AnvilToolkit.App"));
        app.GetType().GetMethod("InitializeComponent", All).Invoke(app, null);
        // InitializeComponent sets StartupUri=MainWindow.xaml; if any toolkit code pumps the dispatcher, WPF would
        // build the main window, whose constructor pops "DirectXTex DLL not found" on the user's desktop
        // (the public setter rejects null, so clear the backing field)
        typeof(System.Windows.Application).GetField("_startupUri", All).SetValue(app, null);
    }
    // safety net: never leave a toolkit window (message box, error, editor) on the user's screen —
    // close it as soon as it loads and log its title instead
    System.Windows.EventManager.RegisterClassHandler(typeof(System.Windows.Window),
        System.Windows.FrameworkElement.LoadedEvent, new System.Windows.RoutedEventHandler((s, _) =>
        {
            var w = (System.Windows.Window)s;
            Console.WriteLine($"# suppressed toolkit window: {w.Title}");
            w.Close();
        }));
    // the toolkit works on the "active game"; Shadows uses forge format 42
    var game = T("AnvilToolkit.Utils.Game");
    T("AnvilToolkit.Utils.DataStorage").GetField("ActiveGame", All).SetValue(null, Enum.Parse(game, "Shadows"));
    // never let the toolkit copy multi-GB forges into a Backups folder next to the game
    var settings = T("AnvilToolkit.Properties.Settings").GetProperty("Default", All).GetValue(null);
    settings.GetType().GetProperty("CreateBackups", All)?.SetValue(settings, false);
    // class/property names (hash -> string) come from an embedded resource loaded on a background task; the GUI does
    // this at startup, and readers crash with a NullReference if they run before it finishes
    var hd = T("AnvilToolkit.Utils.HashedData");
    hd.GetMethod("CheckStrings", All).Invoke(null, null);
    var hsField = hd.GetField("HashedStrings", All);
    for (int i = 0, prev = -1, same = 0; i < 240 && same < 4; i++)
    {
        Thread.Sleep(250);
        var n = (hsField.GetValue(null) as System.Collections.ICollection)?.Count ?? -1;
        same = n > 0 && n == prev ? same + 1 : 0;
        prev = n;
    }
    // Shadows forge entries only carry hashed names; Lists\Shadows.gfl maps them back (loaded on a background task).
    // Without --names, install an empty list instead: names stay as hex IDs and the toolkit never prompts to download.
    var gfl = T("AnvilToolkit.Utils.GameFileList");
    var listField = gfl.GetField("List", All) ?? throw new Exception("GameFileList.List not found");
    if (!args.Contains("--names"))
    {
        listField.SetValue(null, Activator.CreateInstance(listField.FieldType));
        return;
    }
    gfl.GetMethod("CheckStrings", All).Invoke(null, null);
    int last = -1, stable = 0;
    for (int i = 0; i < 600 && stable < 4; i++)
    {
        Thread.Sleep(500);
        var n = (listField.GetValue(null) as System.Collections.ICollection)?.Count ?? -1;
        stable = n > 0 && n == last ? stable + 1 : 0;
        last = n;
    }
    Console.WriteLine($"# file list: {last} names");
}

// the toolkit touches WPF objects, which need a single-threaded apartment
var worker = new Thread(Run);
worker.SetApartmentState(ApartmentState.STA);
worker.Start();
worker.Join();

void Run()
{
switch (args.Length > 0 ? args[0] : "inspect")
{
    case "inspect":
    {
        var rx = new Regex(args.Length > 2 ? args[2] : "forge|locali|patch", RegexOptions.IgnoreCase);
        Type[] types;
        try { types = asm.GetTypes(); } catch (ReflectionTypeLoadException ex) { types = ex.Types.Where(t => t != null).ToArray(); }
        foreach (var t in types.Where(t => rx.IsMatch(t.FullName ?? "")).OrderBy(t => t.FullName))
        {
            Console.WriteLine($"TYPE {t.FullName}");
            if (args.Length > 1 && args[1] == "methods")
                foreach (var m in t.GetMethods(All | BindingFlags.DeclaredOnly).Where(m => !m.IsSpecialName))
                    Console.WriteLine($"    {(m.IsStatic ? "static " : "")}{m.ReturnType.Name} {m.Name}(" +
                                      string.Join(", ", m.GetParameters().Select(p => $"{p.ParameterType.Name} {p.Name}")) + ")");
        }
        break;
    }
    case "list":
    {
        Setup();
        var forgePath = args[1];
        var rx = new Regex(args.Length > 2 ? args[2] : ".", RegexOptions.IgnoreCase);
        var forge = Activator.CreateInstance(T("AnvilToolkit.FileTypes.AnvilNext.Containers.ForgeFile"));
        var game = T("AnvilToolkit.Utils.DataStorage").GetField("ActiveGame", All).GetValue(null);
        // stream:true = read the index only (ForgeDirectory(entriesOnly: true)); nothing is written
        forge.GetType().GetMethod("Deserialize", All).Invoke(forge, new object[] {
            Path.Combine(@"D:\acs-ro\work", "unused"), forgePath, game, false, false, true });
        var dirs = (Array)Get(forge, "Directories");
        int total = 0, shown = 0;
        foreach (var d in dirs)
            foreach (var e in (Array)Get(d, "Entries"))
            {
                total++;
                var name = Get(e, "Name")?.ToString() ?? "";
                var ext = Get(e, "Extension")?.ToString() ?? "";
                // the regex matches the name or the class hash in the Extension field (LocalizationPackage = 1849465967)
                if (!rx.IsMatch(name) && !rx.IsMatch(ext)) continue;
                shown++;
                Console.WriteLine($"{Get(e, "ID")}\t{Get(e, "Offset")}\t{Get(e, "LengthOnDisk")}\t{ext}\t{name}");
            }
        Console.WriteLine($"# {shown} of {total} entries");
        break;
    }
    case "extract":
    {
        // extract <forge> <regex on name|class hash> <outdir>: raw entry bytes -> "<index>_-_<name>.data", as the unpacker does
        Setup();
        var forgePath = args[1];
        var rx = new Regex(args[2], RegexOptions.IgnoreCase);
        var outDir = Directory.CreateDirectory(args[3]).FullName;
        var forge = Activator.CreateInstance(T("AnvilToolkit.FileTypes.AnvilNext.Containers.ForgeFile"));
        var game = T("AnvilToolkit.Utils.DataStorage").GetField("ActiveGame", All).GetValue(null);
        forge.GetType().GetMethod("Deserialize", All).Invoke(forge, new object[] {
            Path.Combine(@"D:\acs-ro\work", "unused"), forgePath, game, false, false, true });
        using var fs = new FileStream(forgePath, FileMode.Open, FileAccess.Read, FileShare.Read);
        int index = 0, n = 0;
        foreach (var d in (Array)Get(forge, "Directories"))
            foreach (var e in (Array)Get(d, "Entries"))
            {
                var name = Get(e, "Name")?.ToString() ?? "";
                var ext = Get(e, "Extension")?.ToString() ?? "";
                if (rx.IsMatch(name) || rx.IsMatch(ext))
                {
                    var buf = new byte[(int)Get(e, "LengthOnDisk")];
                    fs.Position = (long)Get(e, "Offset");
                    fs.ReadExactly(buf);
                    File.WriteAllBytes(Path.Combine(outDir, $"{index}_-_{Path.GetFileNameWithoutExtension(name)}.data"), buf);
                    n++;
                }
                index++;
            }
        Console.WriteLine($"# extracted {n} entries to {outDir}");
        break;
    }
    case "dataunpack":
    {
        // dataunpack <file.data>: DataFile.Deserialize synchronously, with first-chance exceptions printed
        Setup();
        AppDomain.CurrentDomain.FirstChanceException += (_, ev) =>
        {
            if (ev.Exception is NullReferenceException) Console.WriteLine("FIRST-CHANCE NRE:\n" + Environment.StackTrace);
        };
        // a folder unpacks every .data in it that has no Extracted\<name> yet (one process: toolkit loads once)
        var target = Path.GetFullPath(args[1]);
        var files = Directory.Exists(target) ? Directory.GetFiles(target, "*.data") : new[] { target };
        var game = T("AnvilToolkit.Utils.DataStorage").GetField("ActiveGame", All).GetValue(null);
        var dfType = T("AnvilToolkit.FileTypes.AnvilNext.Containers.DataFile");
        int ok = 0, failed = 0;
        foreach (var path in files)
        {
            var xf = Path.Combine(Path.GetDirectoryName(path), "Extracted", Path.GetFileName(path));
            if (Directory.Exists(xf) && Directory.EnumerateFiles(xf).Any()) { ok++; continue; }
            var df = dfType.GetConstructor(new[] { game.GetType() }).Invoke(new[] { game });
            var prop = dfType.GetProperty("ExtractFolder", All);
            if (prop != null) prop.SetValue(df, xf); else dfType.GetField("ExtractFolder", All).SetValue(df, xf);
            var res = dfType.GetMethod("Deserialize", new[] { typeof(string) }).Invoke(df, new object[] { path });
            if (res.ToString().StartsWith("(False")) ok++; else { failed++; Console.WriteLine($"FAIL {path}: {res}"); }
        }
        Console.WriteLine($"# unpacked {ok} ok, {failed} failed");
        break;
    }
    case "exportxml":
    {
        // exportxml <root> <regex>: every matching *.LocalizationPackage under root -> XML next to it (GUI "export")
        Setup();
        var rx = new Regex(args[2], RegexOptions.IgnoreCase);
        var game = T("AnvilToolkit.Utils.DataStorage").GetField("ActiveGame", All).GetValue(null);
        int n = 0;
        var expected = new List<string>();
        foreach (var path in Directory.GetFiles(Path.GetFullPath(args[1]), "*.LocalizationPackage", SearchOption.AllDirectories))
        {
            if (!rx.IsMatch(Path.GetFileName(path))) continue;
            expected.Add(Path.ChangeExtension(path, ".xml"));
            if (File.Exists(Path.ChangeExtension(path, ".xml"))) { n++; continue; }
            // synchronous core of the GUI export (ScimitarFile.ExportXml would open a Save dialog + a background task):
            // new ScimitarFile(path, game).Data.ToXml().WriteToFile(xml)
            var sf = T("AnvilToolkit.FileTypes.AnvilNext.ScimitarFile")
                .GetConstructor(new[] { typeof(string), game.GetType() }).Invoke(new object[] { path, game });
            var data = Get(sf, "Data");
            if (data == null || Get(data, "Failed") is true) { Console.WriteLine($"FAIL read {path}"); continue; }
            // ScimitarClass.ToXml(object obj = null)
            var xel = data.GetType().GetMethod("ToXml", All, new[] { typeof(object) }).Invoke(data, new object[] { null });
            T("AnvilToolkit.Utils.XmlUtils").GetMethod("WriteToFile", All)
                .Invoke(null, new object[] { xel, Path.ChangeExtension(path, ".xml"), 0, false });
            n++;
        }
        Console.WriteLine($"# exported {expected.Count(File.Exists)} of {expected.Count} packages");
        break;
    }
    case "importxml":
    {
        // importxml <xml> <target.LocalizationPackage>: XmlUtils.CompileXml (the GUI "import XML" minus its file dialog)
        Setup();
        var ok = T("AnvilToolkit.Utils.XmlUtils").GetMethod("CompileXml", All, new[] { typeof(string), typeof(string) })
            .Invoke(null, new object[] { Path.GetFullPath(args[1]), Path.GetFullPath(args[2]) });
        Console.WriteLine($"# CompileXml -> {ok}");
        break;
    }
    case "repackdata":
    {
        // repackdata <extracted folder> <original .data> <output .data>: synchronous core of DataFile.Serialize(path)
        Setup();
        var game = T("AnvilToolkit.Utils.DataStorage").GetField("ActiveGame", All).GetValue(null);
        var dfType = T("AnvilToolkit.FileTypes.AnvilNext.Containers.DataFile");
        var folder = Path.GetFullPath(args[1]);
        foreach (var dep in Directory.GetFiles(folder, "*.Dependency")) File.Delete(dep);  // as the toolkit does
        object oldMeta;
        using (var br = new BinaryReader(new MemoryStream(File.ReadAllBytes(args[2]))))
            oldMeta = dfType.GetMethod("GetMetaData", All).Invoke(null, new object[] { br, game });
        var df = dfType.GetConstructor(new[] { game.GetType() }).Invoke(new[] { game });
        object res;
        using (var fs = new FileStream(args[3], FileMode.Create, FileAccess.ReadWrite, FileShare.None))
            res = dfType.GetMethod("Serialize", new[] { typeof(Stream), typeof(string), oldMeta?.GetType() ??
                      T("AnvilToolkit.FileTypes.AnvilNext.Containers.MetaData"), typeof(bool) })
                .Invoke(df, new object[] { fs, folder, oldMeta, false });
        Console.WriteLine($"# DataFile.Serialize -> {res} ({new FileInfo(args[3]).Length} bytes)");
        break;
    }
    case "repackall":
    {
        // repackall <root>: for every <root>\X.data with an unpacked <root>\Extracted\X.data folder, write <root>\out\X.data
        Setup();
        var game = T("AnvilToolkit.Utils.DataStorage").GetField("ActiveGame", All).GetValue(null);
        var dfType = T("AnvilToolkit.FileTypes.AnvilNext.Containers.DataFile");
        // DataFile.Serialize(Stream, string ExtractedFolder, MetaData oldMetaData, bool Lock)
        var serialize = dfType.GetMethods(All).First(m => m.Name == "Serialize" &&
            m.GetParameters().Length == 4 && m.GetParameters()[0].ParameterType == typeof(Stream));
        var root = Path.GetFullPath(args[1]);
        var outDir = Directory.CreateDirectory(Path.Combine(root, "out")).FullName;
        int ok = 0, failed = 0;
        foreach (var orig in Directory.GetFiles(root, "*.data"))
        {
            var folder = Path.Combine(root, "Extracted", Path.GetFileName(orig));
            if (!Directory.Exists(folder)) continue;
            foreach (var dep in Directory.GetFiles(folder, "*.Dependency")) File.Delete(dep);
            object oldMeta;
            using (var br = new BinaryReader(new MemoryStream(File.ReadAllBytes(orig))))
                oldMeta = dfType.GetMethod("GetMetaData", All).Invoke(null, new object[] { br, game });
            var df = dfType.GetConstructor(new[] { game.GetType() }).Invoke(new[] { game });
            var target = Path.Combine(outDir, Path.GetFileName(orig));
            object res;
            using (var fs = new FileStream(target, FileMode.Create, FileAccess.ReadWrite, FileShare.None))
                res = serialize.Invoke(df, new object[] { fs, folder, oldMeta, false });
            if (res.ToString().StartsWith("(False")) ok++; else { failed++; Console.WriteLine($"FAIL {orig}: {res}"); }
        }
        Console.WriteLine($"# repacked {ok} ok, {failed} failed into {outDir}");
        break;
    }
    case "buildpatch":
    {
        // buildpatch <head forge> <work dir> <out forge> <.data ...> [--prefetch-from forge1;forge2...]
        // 1. ForgeFile.CreateNewPatchForge(head) = boot-safe empty shell (carries the prefetch graph), written + unpacked
        // 2. the .data files go into the unpacked folder; their PrefetchFileInfoObject is copied from the forge chain
        // 3. the folder is repacked into the new forge
        Setup();
        var game = T("AnvilToolkit.Utils.DataStorage").GetField("ActiveGame", All).GetValue(null);
        var ffType = T("AnvilToolkit.FileTypes.AnvilNext.Containers.ForgeFile");
        var pfiType = T("AnvilToolkit.FileTypes.AnvilNext.Containers.PrefetchingFileInfos");
        string head = Path.GetFullPath(args[1]), work = Path.GetFullPath(args[2]), outForge = Path.GetFullPath(args[3]);
        Directory.CreateDirectory(Path.GetDirectoryName(outForge));
        var dataFiles = args.Skip(4).TakeWhile(a => !a.StartsWith("--")).Select(Path.GetFullPath).ToList();
        var chain = args.SkipWhile(a => a != "--prefetch-from").Skip(1).FirstOrDefault()?.Split(';') ?? new[] { head };
        Directory.CreateDirectory(work);
        var shellPath = Path.Combine(work, Path.GetFileName(outForge));
        var shell = ffType.GetMethod("CreateNewPatchForge", All).Invoke(null, new object[] { head })
                    ?? throw new Exception("CreateNewPatchForge returned null");
        ((Task)ffType.GetMethod("Serialize", All, new[] { typeof(string), typeof(string), game.GetType() })
            .Invoke(shell, new object[] { "", shellPath, game })).Wait();
        Console.WriteLine($"# shell written: {shellPath} ({new FileInfo(shellPath).Length} bytes)");
        // unpack the shell like the GUI does (into <work>\Extracted\<name>.forge)
        var extracted = Path.Combine(work, "Extracted");
        var unpacked = Path.Combine(extracted, Path.GetFileName(shellPath));
        if (Directory.Exists(unpacked)) Directory.Delete(unpacked, true);
        var reader = Activator.CreateInstance(ffType);
        ffType.GetMethod("Deserialize", All).Invoke(reader, new object[] { extracted, shellPath, game, false, false, false });
        var metaFiles = Directory.GetFiles(unpacked);
        Console.WriteLine($"# shell unpacked: {string.Join(", ", metaFiles.Select(Path.GetFileName))}");
        // prefetch objects for our .data IDs, newest forge in the chain first
        var ids = dataFiles.ToDictionary(f => Convert.ToUInt64(Path.GetFileNameWithoutExtension(f).Split("_-_").Last(), 16), f => f);
        var found = new Dictionary<ulong, object>();
        foreach (var forgePath in chain)
        {
            var f = Activator.CreateInstance(ffType);
            ffType.GetMethod("Deserialize", All).Invoke(f, new object[] { Path.Combine(work, "unused"), forgePath, game, false, false, true });
            using var fs = new FileStream(forgePath, FileMode.Open, FileAccess.Read, FileShare.Read);
            foreach (var d in (Array)Get(f, "Directories"))
                foreach (var e in (Array)Get(d, "Entries"))
                {
                    if ((ulong)Get(e, "ID") != 145) continue;
                    var buf = new byte[(int)Get(e, "LengthOnDisk")];
                    fs.Position = (long)Get(e, "Offset");
                    fs.ReadExactly(buf);
                    var pfi = pfiType.GetConstructor(new[] { typeof(byte[]), game.GetType() }).Invoke(new object[] { buf, game });
                    Console.WriteLine($"# {Path.GetFileName(forgePath)}: {((System.Collections.ICollection)Get(pfi, "Objects")).Count} prefetch objects");
                    foreach (var o in (System.Collections.IEnumerable)Get(pfi, "Objects"))
                    {
                        var oid = (ulong)Get(o, "ID");
                        if (ids.ContainsKey(oid) && !found.ContainsKey(oid)) found[oid] = o;
                    }
                }
            if (Directory.Exists(Path.Combine(work, "unused"))) Directory.Delete(Path.Combine(work, "unused"), true);
        }
        Console.WriteLine($"# prefetch objects found for {found.Count} of {ids.Count} data files");
        // add them to the shell's (empty) PrefetchingFileInfos
        var pfiFile = metaFiles.Single(m => m.EndsWith(".PrefetchInfo", StringComparison.OrdinalIgnoreCase));
        var mine = pfiType.GetConstructor(new[] { typeof(string), game.GetType() }).Invoke(new object[] { pfiFile, game });
        var list = (System.Collections.IList)Get(mine, "Objects");
        foreach (var o in found.Values) list.Add(o);
        var bytes = (byte[])pfiType.GetMethod("Serialize", All, new[] { game.GetType() }).Invoke(mine, new[] { game });
        File.WriteAllBytes(pfiFile, bytes);
        // copy the .data files after the 5 meta files, keeping the "<index>_-_<HEXID>.data" naming the repacker parses
        int idx = metaFiles.Length;
        foreach (var (id, f) in ids)
            File.Copy(f, Path.Combine(unpacked, $"{idx++}_-_{id:X16}.data"), true);
        // repack the folder (GUI "repack folder": ForgeFile.SerializeAsync(folder, forge)) synchronously
        var packer = Activator.CreateInstance(ffType);
        ((Task)ffType.GetMethod("Serialize", All, new[] { typeof(string), typeof(string), game.GetType() })
            .Invoke(packer, new object[] { unpacked, outForge, game })).Wait();
        Console.WriteLine($"# built {outForge} ({new FileInfo(outForge).Length} bytes)");
        break;
    }
    case "process":
    {
        // process <file> <action>: FileHandler.ProcessFile, i.e. the GUI's unpack/export (0) or repack/import (1, 2 = folder)
        Setup();
        var path = Path.GetFullPath(args[1]);
        var model = Activator.CreateInstance(T("AnvilToolkit.Windows.FileModel"));
        void SetM(string member, object v)
        {
            var p = model.GetType().GetProperty(member, All);
            if (p != null && p.CanWrite) p.SetValue(model, v); else model.GetType().GetField(member, All)?.SetValue(model, v);
        }
        var isDir = Directory.Exists(path);
        SetM("Name", Path.GetFileName(path));
        SetM("Path", path);
        SetM("Extension", isDir ? "" : Path.GetExtension(path).TrimStart('.'));
        var ftype = model.GetType().GetProperty("Type", All).PropertyType;
        SetM("Type", Enum.Parse(ftype, isDir ? "Folder" : "File"));
        var res = T("AnvilToolkit.FileHandler").GetMethod("ProcessFile", All)
            .Invoke(null, new object[] { model, int.Parse(args[2]), 0, false, false });
        Console.WriteLine($"# ProcessFile -> {res}");
        // unpack/export run on background threads in the toolkit; give them time to finish writing
        Thread.Sleep(args.Length > 3 ? int.Parse(args[3]) : 5000);
        break;
    }
}
}
