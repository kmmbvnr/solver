/* Construct or independently evaluate one XHSTT solution with KHE. */
#include <stdio.h>
#include <stdlib.h>
#include "khe.h"

int main(int argc, char **argv) {
    if (argc != 4) return 1;
    FILE *input = fopen(argv[1], "r");
    KHE_ARCHIVE archive;
    KML_ERROR error;
    if (!input || !KheArchiveRead(input, &archive, true, &error)) return 1;
    fclose(input);
    if (KheArchiveInstanceCount(archive) != 1) return 1;
    KHE_SOLN sol;
    if (atoi(argv[3]) < 0) {
        if (KheArchiveSolnGroupCount(archive) != 1) return 1;
        KHE_SOLN_GROUP group = KheArchiveSolnGroup(archive, 0);
        if (KheSolnGroupSolnCount(group) != 1) return 1;
        sol = KheSolnGroupSoln(group, 0);
    } else {
        if (KheArchiveSolnGroupCount(archive) != 0) return 1;
        KHE_SOLN_GROUP group;
        KHE_SOLN_GROUP_METADATA meta = KheSolnGroupMetaDataMake(
            "ShiftOpt", "2026", "Diversified KHE construction", "ITC 2011");
        if (!KheSolnGroupMake(archive, "ShiftOpt", meta, &group)) return 1;
        sol = KheSolnMake(KheArchiveInstance(archive, 0), group);
        KheSolnSetDiversifier(sol, atoi(argv[3]));
        sol = KheGeneralSolve(sol);
    }
    KheSolnEnsureOfficialCost(sol);
    KHE_COST cost = KheSolnCost(sol);
    if (atoi(argv[3]) >= 0) {
        FILE *output = fopen(argv[2], "w");
        if (!output || !KheArchiveWrite(archive, true, output)) return 1;
        fclose(output);
    }
    printf("Cost %d %d\n", KheHardCost(cost), KheSoftCost(cost));
    return 0;
}
