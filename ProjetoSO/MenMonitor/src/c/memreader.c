#include <windows.h> 
#include <psapi.h> 
#include <stdio.h> 

typedef struct {
    double commitMB; 
    double reserveMB; 
    double freeMB; 
} MemResumo;

typedef struct {
    unsigned long long baseAddress;
    unsigned long long regionSize;
    DWORD state;  // MEM_COMMIT, MEM_RESERVE, MEM_FREE
} MemBloco;

//ABA 1 ------------------- Monitor de memoria
__declspec(dllexport)
MemResumo listar_resumo(DWORD pid) {

    MemResumo resumo = {0}; 
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);

    if (!hProcess) {
        return resumo;
    }

    SYSTEM_INFO sysInfo;
    GetSystemInfo(&sysInfo);

    MEMORY_BASIC_INFORMATION mbi;
    unsigned char* addr = 0;
    SIZE_T totalCommit = 0, totalReserve = 0, totalFree = 0;

    while (addr < (unsigned char*)sysInfo.lpMaximumApplicationAddress) {
        SIZE_T result = VirtualQueryEx(hProcess, addr, &mbi, sizeof(mbi));
        if (result == 0)
            break;

        if (mbi.State == MEM_COMMIT) 
            totalCommit += mbi.RegionSize;
        else if (mbi.State == MEM_RESERVE) 
            totalReserve += mbi.RegionSize;
        else if (mbi.State == MEM_FREE) 
            totalFree += mbi.RegionSize;

        addr += mbi.RegionSize;
    }

    CloseHandle(hProcess);

    resumo.commitMB  = totalCommit  / (1024.0 * 1024);
    resumo.reserveMB = totalReserve / (1024.0 * 1024);
    resumo.freeMB    = totalFree    / (1024.0 * 1024);

    return resumo;
}

//ABA 2 ------------------- Page faults
__declspec(dllexport)
DWORD obter_page_faults(DWORD pid) {
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (!hProcess) {
        return 0;
    }

    PROCESS_MEMORY_COUNTERS pmc; //essa estrutura vai armazenar estatiscas de memoria do processo, como working set, page fautls, tamanho de memoria privada, uso de memoria fisica, swap
    //extrai somente o campo PageFaultCount

    if (!GetProcessMemoryInfo(hProcess, &pmc, sizeof(pmc))) {
        CloseHandle(hProcess);
        return 0;
    }

    CloseHandle(hProcess);
    return pmc.PageFaultCount;
}

//ABA 3 ------------------- Swap
__declspec(dllexport)
double obter_swap_mb(DWORD pid) {
    PROCESS_MEMORY_COUNTERS_EX pmc;
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (!hProcess) return 0;

    //ler informações de memoria do processo, ele está preenchendo as informações WorkingSetSize e PrivateUsage 
    if (!GetProcessMemoryInfo(hProcess, (PROCESS_MEMORY_COUNTERS*)&pmc, sizeof(pmc))) {
        CloseHandle(hProcess);
        return 0;
    }

    CloseHandle(hProcess);

    //privateUsage é oq está na RAM e no SWAP 
    //workingSet é oq está na RAM
    //swap = (RAM + SWAP) – RAM
    double workingSetMB   = pmc.WorkingSetSize / (1024.0 * 1024);
    double privateUsageMB = pmc.PrivateUsage  / (1024.0 * 1024);
    double swapMB         = privateUsageMB - workingSetMB;

   
    if (swapMB < 0) swapMB = 0;
    return swapMB;
}

//ABA 4 ------------------- Fragmentação de Memoria
__declspec(dllexport)
int listar_fragmentacao(DWORD pid, MemBloco* buffer, int maxBlocos) { //buffer: vetor de estruturas onde é gravados os blocos

    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (!hProcess)
        return -1;

    SYSTEM_INFO sysInfo;
    GetSystemInfo(&sysInfo);

    //addr é um ponteiro que começa no endereço virtual zero e vai até o final
    // lpMaximumApplicationAddress é o endereço final da memória virtual do processo
    // faz o loop de toda a memoria virtual
    MEMORY_BASIC_INFORMATION mbi;
    unsigned char* addr = 0;
    int count = 0;
 
    while (addr < (unsigned char*)sysInfo.lpMaximumApplicationAddress) {

        SIZE_T result = VirtualQueryEx(hProcess, addr, &mbi, sizeof(mbi));
        if (result == 0)
            break;
        //vai gravando até o limite de 4096, passou disso para de gravar
        if (count < maxBlocos && buffer != NULL) {
            buffer[count].baseAddress = (unsigned long long)mbi.BaseAddress;
            buffer[count].regionSize  = (unsigned long long)mbi.RegionSize;
            buffer[count].state       = mbi.State;
        }

        count++;
        addr += mbi.RegionSize;
    }

    CloseHandle(hProcess);
    return count;   // total de blocos encontrados
}