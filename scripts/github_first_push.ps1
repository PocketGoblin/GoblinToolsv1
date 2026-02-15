param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUrl,
    [string]$Branch = "main"
)

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is not installed or not on PATH."
}

$userName = git config --get user.name
$userEmail = git config --get user.email
if (-not $userName -or -not $userEmail) {
    throw "Set git identity first: git config --global user.name `"Your Name`"; git config --global user.email `"you@example.com`""
}

git init
git add .
git commit -m "chore: initial v1.0.0 release"
git branch -M $Branch
$existing = git remote
if ($existing -contains "origin") {
    git remote set-url origin $RemoteUrl
} else {
    git remote add origin $RemoteUrl
}
git push -u origin $Branch
