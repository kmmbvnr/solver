open System
open System.Threading
open System.Xml.Linq
open Timetabling.Common
open Timetabling.Common.Domain

let args = fsi.CommandLineArgs
let parsed = Problem.parse (XDocument.Load(args.[1]).Root)
let problem = match parsed with Ok p -> p | Error e -> failwithf "%A" e
let seed = int args.[4]
let timer = new CancellationTokenSource(TimeSpan.FromSeconds(float args.[3]))
let initial =
    if args.Length <= 5 then Problem.initialSolution problem
    else
        match Problem.parseSolution problem (XDocument.Load(args.[5]).Root) with
        | Ok s -> s
        | Error e -> failwithf "%A" e
let best, elapsed = Solver.solve seed timer.Token problem initial
if best.HardPenalty = 0 && best.ClassCapacityPenalty() = 0 then
    let info = { SolverInfo.defaults with Author = "ShiftOpt"; Technique = "Gashi construction"; Institution = ""; Country = "" }
    (Solution.serialize info problem seed elapsed best).Save(args.[2])
    printfn "COST %d" best.SoftPenalty
